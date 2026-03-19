"""
IOlabs AI SDR Platform — Stage 1: Lead Discovery Worker (Step 6)

Queue: {client_id}_discovery
Task:  run_discovery(client_id)

Flow:
  1. Load client config
  2. For each google_category in config.discovery.google_categories:
     - SerpAPI Google Maps: "{category} in {target_geo}"
     - Parse: name, address, phone, website, category, rating, review_count, place_id
     - Deduplicate by place_id OR website domain against existing leads
     - INSERT new leads with status='raw'
  3. Enqueue classify_lead for each new lead → {client_id}_classify queue
  4. Log run summary to platform.audit_log

Edge cases handled:
  - SerpAPI rate limit: exponential backoff 30s → 60s → 120s (Section 11)
  - Duplicate lead: silent skip + log entry (Section 11)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from urllib.parse import urlparse

import requests
from sqlalchemy import select, text

from iolabs_sdr.core.celery_app import app
from iolabs_sdr.core.config_loader import load_client_config
from iolabs_sdr.core.exceptions import SerpAPIError, SerpAPIRateLimitError
from iolabs_sdr.db.models import AuditLog, Lead
from iolabs_sdr.db.session import get_client_session, get_platform_session

logger = logging.getLogger(__name__)

# ── SerpAPI ────────────────────────────────────────────────────────────────────

_SERPAPI_URL = "https://serpapi.com/search.json"
_MAX_PAGES_PER_CATEGORY = 3      # up to 60 results per category
_RESULTS_PER_PAGE = 20
_SERPAPI_TIMEOUT = 15            # seconds per HTTP request

# Rate-limit backoff delays (seconds): 30 → 60 → 120
_RATE_LIMIT_BACKOFFS = [30, 60, 120]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_serpapi_key() -> str:
    key = os.environ.get("SERPAPI_API_KEY", "")
    if not key:
        raise SerpAPIError(
            "SERPAPI_API_KEY environment variable is not set. "
            "Set it before running the discovery worker."
        )
    return key


def _extract_domain(url: str | None) -> str | None:
    """Return the bare domain (no www prefix) from a URL, or None."""
    if not url:
        return None
    try:
        parsed = urlparse(url if url.startswith("http") else f"http://{url}")
        domain = parsed.netloc.lower()
        return domain.lstrip("www.") if domain else None
    except Exception:
        return None


def _search_serpapi_page(query: str, start: int, api_key: str) -> list[dict]:
    """
    Fetch a single page of Google Maps results from SerpAPI.

    Raises:
        SerpAPIRateLimitError: On HTTP 429.
        SerpAPIError: On any other non-200 response or network failure.
    """
    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
        "start": start,
        "api_key": api_key,
    }
    try:
        resp = requests.get(_SERPAPI_URL, params=params, timeout=_SERPAPI_TIMEOUT)
    except requests.RequestException as exc:
        raise SerpAPIError(f"SerpAPI network error: {exc}") from exc

    if resp.status_code == 429:
        raise SerpAPIRateLimitError(f"SerpAPI rate limit hit (HTTP 429) for query: {query!r}")
    if resp.status_code != 200:
        raise SerpAPIError(
            f"SerpAPI returned HTTP {resp.status_code} for query {query!r}: {resp.text[:200]}"
        )

    data = resp.json()
    return data.get("local_results") or []


def _fetch_category_results(category: str, target_geo: str, api_key: str) -> list[dict]:
    """
    Fetch all pages for one category query with exponential backoff on rate limits.

    Returns a flat list of raw SerpAPI result dicts.
    """
    query = f"{category} in {target_geo}"
    all_results: list[dict] = []

    for page in range(_MAX_PAGES_PER_CATEGORY):
        start = page * _RESULTS_PER_PAGE
        backoff_index = 0

        while True:
            try:
                page_results = _search_serpapi_page(query, start, api_key)
                all_results.extend(page_results)
                logger.debug(
                    "SerpAPI query=%r start=%d → %d results",
                    query, start, len(page_results),
                )
                # Fewer results than a full page → no more pages
                if len(page_results) < _RESULTS_PER_PAGE:
                    return all_results
                break  # success — advance to next page

            except SerpAPIRateLimitError as exc:
                if backoff_index >= len(_RATE_LIMIT_BACKOFFS):
                    logger.error("SerpAPI rate limit: exhausted backoff retries for %r", query)
                    raise
                delay = _RATE_LIMIT_BACKOFFS[backoff_index]
                logger.warning(
                    "SerpAPI rate limit hit for %r. Backing off %ds (attempt %d/3).",
                    query, delay, backoff_index + 1,
                )
                time.sleep(delay)
                backoff_index += 1

    return all_results


def _parse_result(raw: dict) -> dict:
    """
    Map a raw SerpAPI Google Maps result dict to our Lead column dict.
    All fields are optional except name (which SerpAPI always returns as 'title').
    """
    return {
        "place_id": raw.get("place_id"),
        "name": raw.get("title", "").strip() or "Unknown",
        "address": raw.get("address"),
        "phone": raw.get("phone"),
        "website": raw.get("website"),
        "google_category": raw.get("type"),
        "rating": _safe_float(raw.get("rating")),
        "review_count": _safe_int(raw.get("reviews")),
    }


def _safe_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ── Async DB helpers ───────────────────────────────────────────────────────────


async def _load_existing_sets(client_id: str) -> tuple[set[str], set[str]]:
    """
    Return (existing_place_ids, existing_domains) from the client's leads table.
    Used for deduplication.
    """
    existing_place_ids: set[str] = set()
    existing_domains: set[str] = set()

    async with get_client_session(client_id) as session:
        result = await session.execute(
            select(Lead.place_id, Lead.website)
        )
        for place_id, website in result:
            if place_id:
                existing_place_ids.add(place_id)
            domain = _extract_domain(website)
            if domain:
                existing_domains.add(domain)

    return existing_place_ids, existing_domains


async def _insert_leads_batch(
    client_id: str,
    leads_data: list[dict],
) -> list[int]:
    """
    INSERT leads into the client schema.
    Returns list of new lead IDs.

    Each dict in leads_data must have at least: name.
    Optional: place_id, address, phone, website, google_category, rating, review_count.
    """
    new_ids: list[int] = []

    async with get_client_session(client_id) as session:
        for data in leads_data:
            lead = Lead(**data)
            session.add(lead)
            await session.flush()   # get auto-generated id before commit
            new_ids.append(lead.id)
        await session.commit()

    return new_ids


async def _write_audit_log(
    client_id: str,
    stage: str,
    action: str,
    status: str,
    message: str,
    entity_id: str | None = None,
) -> None:
    """Write a single entry to platform.audit_log."""
    async with get_platform_session() as session:
        entry = AuditLog(
            client_id=client_id,
            stage=stage,
            action=action,
            entity_id=entity_id,
            status=status,
            message=message,
        )
        session.add(entry)
        await session.commit()


# ── Core async logic ───────────────────────────────────────────────────────────


async def _run_discovery_async(client_id: str) -> dict:
    """
    Full async discovery logic — called from the sync Celery task via asyncio.run().

    Returns:
        dict with keys: new_leads (int), duplicates (int), errors (int)
    """
    config = load_client_config(client_id)
    api_key = _get_serpapi_key()

    discovery = config.discovery
    categories: list[str] = discovery.google_categories
    target_geo: str = discovery.target_geo

    # Load existing sets for deduplication
    existing_place_ids, existing_domains = await _load_existing_sets(client_id)

    new_count = 0
    dup_count = 0
    err_count = 0
    new_lead_ids: list[int] = []
    batch: list[dict] = []

    for category in categories:
        try:
            raw_results = _fetch_category_results(category, target_geo, api_key)
        except SerpAPIError as exc:
            logger.error("Discovery SerpAPI error for %r/%r: %s", client_id, category, exc)
            err_count += 1
            await _write_audit_log(
                client_id=client_id,
                stage="discovery",
                action="serpapi_fetch",
                status="error",
                message=f"category={category!r}: {exc}",
            )
            continue

        for raw in raw_results:
            parsed = _parse_result(raw)

            # ── Deduplication ──────────────────────────────────────────────────
            place_id = parsed.get("place_id")
            domain = _extract_domain(parsed.get("website"))

            is_dup = False
            if place_id and place_id in existing_place_ids:
                is_dup = True
            elif domain and domain in existing_domains:
                is_dup = True

            if is_dup:
                dup_count += 1
                logger.debug(
                    "Duplicate lead skipped: place_id=%r domain=%r", place_id, domain
                )
                continue

            # Mark as seen so later results in the same run don't duplicate
            if place_id:
                existing_place_ids.add(place_id)
            if domain:
                existing_domains.add(domain)

            batch.append(parsed)

    # Bulk-insert all new leads
    if batch:
        try:
            new_lead_ids = await _insert_leads_batch(client_id, batch)
            new_count = len(new_lead_ids)
        except Exception as exc:
            logger.error("Discovery DB insert error for %r: %s", client_id, exc)
            err_count += len(batch)
            new_lead_ids = []

    # Enqueue classify_lead for each new lead
    classify_queue = f"{client_id}_classify"
    for lead_id in new_lead_ids:
        app.send_task(
            "iolabs_sdr.workers.classify.classify_lead",
            kwargs={"lead_id": lead_id, "client_id": client_id},
            queue=classify_queue,
        )

    # Audit log summary
    summary_msg = (
        f"Discovery complete: new={new_count} duplicates={dup_count} errors={err_count} "
        f"categories={len(categories)} geo={target_geo!r}"
    )
    await _write_audit_log(
        client_id=client_id,
        stage="discovery",
        action="run_discovery",
        status="success" if err_count == 0 else "partial_error",
        message=summary_msg,
    )

    logger.info("run_discovery[%s]: %s", client_id, summary_msg)
    return {"new_leads": new_count, "duplicates": dup_count, "errors": err_count}


# ── Celery task ────────────────────────────────────────────────────────────────


@app.task(
    name="iolabs_sdr.workers.discovery.run_discovery",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_discovery(self, client_id: str) -> dict:
    """
    Celery task: discover leads for the given client via SerpAPI Google Maps.

    Queue:   {client_id}_discovery
    Retries: up to 3 times on unexpected error (60s delay).
             SerpAPI rate limits are handled internally with exponential backoff.

    Returns:
        dict: {new_leads: int, duplicates: int, errors: int}
    """
    try:
        return asyncio.run(_run_discovery_async(client_id))
    except SerpAPIError as exc:
        logger.error("run_discovery[%s] SerpAPI failure: %s", client_id, exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("run_discovery[%s] unexpected error: %s", client_id, exc)
        raise self.retry(exc=exc)
