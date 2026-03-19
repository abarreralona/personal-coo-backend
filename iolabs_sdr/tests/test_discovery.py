"""
Tests for workers/discovery.py — Step 6.

All external calls (SerpAPI, DB, Celery) are mocked.
Tests verify:
  - _extract_domain: URL parsing + www stripping
  - _parse_result: SerpAPI dict → Lead column dict
  - _safe_float / _safe_int: type coercion edge cases
  - _fetch_category_results: pagination, rate-limit backoff, early-exit on partial page
  - _run_discovery_async: deduplication, bulk insert, classify enqueue, audit log
  - run_discovery (Celery task): Celery retry on unexpected error
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from iolabs_sdr.core.exceptions import SerpAPIError, SerpAPIRateLimitError
from iolabs_sdr.workers.discovery import (
    _extract_domain,
    _fetch_category_results,
    _parse_result,
    _run_discovery_async,
    _safe_float,
    _safe_int,
    _search_serpapi_page,
)


# ── _extract_domain ────────────────────────────────────────────────────────────


class TestExtractDomain:
    def test_basic_https_url(self):
        assert _extract_domain("https://www.acme.com") == "acme.com"

    def test_basic_http_url(self):
        assert _extract_domain("http://acme.com/products") == "acme.com"

    def test_no_www_prefix(self):
        assert _extract_domain("https://acme.com") == "acme.com"

    def test_subdomain_preserved(self):
        assert _extract_domain("https://shop.acme.com") == "shop.acme.com"

    def test_url_without_scheme(self):
        assert _extract_domain("acme.com") == "acme.com"

    def test_none_returns_none(self):
        assert _extract_domain(None) is None

    def test_empty_string_returns_none(self):
        assert _extract_domain("") is None

    def test_uppercase_normalized_to_lower(self):
        assert _extract_domain("https://ACME.COM") == "acme.com"


# ── _parse_result ──────────────────────────────────────────────────────────────


class TestParseResult:
    def test_full_result(self):
        raw = {
            "title": "Acme Packaging Co.",
            "place_id": "abc123",
            "address": "123 Main St, Austin TX",
            "phone": "+1-512-555-1234",
            "website": "https://acme.com",
            "type": "Packaging company",
            "rating": 4.7,
            "reviews": 89,
        }
        parsed = _parse_result(raw)
        assert parsed["name"] == "Acme Packaging Co."
        assert parsed["place_id"] == "abc123"
        assert parsed["address"] == "123 Main St, Austin TX"
        assert parsed["phone"] == "+1-512-555-1234"
        assert parsed["website"] == "https://acme.com"
        assert parsed["google_category"] == "Packaging company"
        assert parsed["rating"] == 4.7
        assert parsed["review_count"] == 89

    def test_missing_optional_fields(self):
        raw = {"title": "Minimal Corp"}
        parsed = _parse_result(raw)
        assert parsed["name"] == "Minimal Corp"
        assert parsed["place_id"] is None
        assert parsed["phone"] is None
        assert parsed["website"] is None

    def test_empty_title_becomes_unknown(self):
        raw = {"title": "   "}
        assert _parse_result(raw)["name"] == "Unknown"

    def test_rating_coerced_to_float(self):
        raw = {"title": "X", "rating": "4.5"}
        assert _parse_result(raw)["rating"] == 4.5

    def test_reviews_coerced_to_int(self):
        raw = {"title": "X", "reviews": "123"}
        assert _parse_result(raw)["review_count"] == 123


# ── _safe_float / _safe_int ────────────────────────────────────────────────────


class TestSafeCoercions:
    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_string(self):
        assert _safe_float("3.14") == 3.14

    def test_safe_float_invalid(self):
        assert _safe_float("not-a-number") is None

    def test_safe_int_none(self):
        assert _safe_int(None) is None

    def test_safe_int_float_truncates(self):
        assert _safe_int(4.9) == 4

    def test_safe_int_invalid(self):
        assert _safe_int("abc") is None


# ── _search_serpapi_page ───────────────────────────────────────────────────────


class TestSearchSerpapiPage:
    def test_returns_local_results(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "local_results": [{"title": "A"}, {"title": "B"}]
        }
        with patch("requests.get", return_value=mock_resp):
            results = _search_serpapi_page("packaging TX", 0, "KEY")
        assert results == [{"title": "A"}, {"title": "B"}]

    def test_empty_response_returns_empty_list(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        with patch("requests.get", return_value=mock_resp):
            assert _search_serpapi_page("q", 0, "KEY") == []

    def test_429_raises_rate_limit_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(SerpAPIRateLimitError):
                _search_serpapi_page("q", 0, "KEY")

    def test_500_raises_serpapi_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(SerpAPIError):
                _search_serpapi_page("q", 0, "KEY")

    def test_network_exception_raises_serpapi_error(self):
        import requests as req
        with patch("requests.get", side_effect=req.RequestException("timeout")):
            with pytest.raises(SerpAPIError):
                _search_serpapi_page("q", 0, "KEY")


# ── _fetch_category_results ────────────────────────────────────────────────────


class TestFetchCategoryResults:
    def _make_n_results(self, n: int) -> list[dict]:
        return [{"title": f"Lead {i}", "place_id": f"p{i}"} for i in range(n)]

    def test_single_page_below_limit_stops(self):
        """Fewer than 20 results → only one page fetched."""
        with patch(
            "iolabs_sdr.workers.discovery._search_serpapi_page",
            return_value=self._make_n_results(5),
        ) as mock_search:
            results = _fetch_category_results("packaging", "Texas", "KEY")
        assert mock_search.call_count == 1
        assert len(results) == 5

    def test_full_page_triggers_next_page(self):
        """Exactly 20 results on page 1 → page 2 is fetched."""
        page1 = self._make_n_results(20)
        page2 = self._make_n_results(5)   # partial page → stop
        with patch(
            "iolabs_sdr.workers.discovery._search_serpapi_page",
            side_effect=[page1, page2],
        ) as mock_search:
            results = _fetch_category_results("packaging", "Texas", "KEY")
        assert mock_search.call_count == 2
        assert len(results) == 25

    def test_rate_limit_triggers_backoff_then_succeeds(self):
        """One rate-limit error → sleep → retry succeeds."""
        page = self._make_n_results(5)
        with (
            patch(
                "iolabs_sdr.workers.discovery._search_serpapi_page",
                side_effect=[SerpAPIRateLimitError("429"), page],
            ),
            patch("time.sleep") as mock_sleep,
        ):
            results = _fetch_category_results("packaging", "Texas", "KEY")
        mock_sleep.assert_called_once_with(30)  # first backoff = 30s
        assert len(results) == 5

    def test_exhausted_backoff_raises(self):
        """Four consecutive rate-limit errors → raises after 3 backoffs."""
        with (
            patch(
                "iolabs_sdr.workers.discovery._search_serpapi_page",
                side_effect=SerpAPIRateLimitError("429"),
            ),
            patch("time.sleep"),
        ):
            with pytest.raises(SerpAPIRateLimitError):
                _fetch_category_results("packaging", "Texas", "KEY")

    def test_max_pages_cap(self):
        """Even if each page is full, stop after MAX_PAGES_PER_CATEGORY pages."""
        full_page = self._make_n_results(20)
        with patch(
            "iolabs_sdr.workers.discovery._search_serpapi_page",
            return_value=full_page,
        ) as mock_search:
            results = _fetch_category_results("packaging", "Texas", "KEY")
        assert mock_search.call_count == 3  # _MAX_PAGES_PER_CATEGORY = 3
        assert len(results) == 60


# ── _run_discovery_async ───────────────────────────────────────────────────────


def _make_fake_config(categories=None, geo="Texas, USA"):
    config = MagicMock()
    config.discovery.google_categories = categories or ["packaging company"]
    config.discovery.target_geo = geo
    return config


def _make_lead_row(place_id=None, website=None):
    row = MagicMock()
    row.__iter__ = MagicMock(return_value=iter([place_id, website]))
    return row


def _serpapi_result(place_id="pid1", name="Acme Co", website="https://acme.com"):
    return {
        "place_id": place_id,
        "title": name,
        "address": "123 Main",
        "phone": "555-1234",
        "website": website,
        "type": "Packaging company",
        "rating": 4.5,
        "reviews": 42,
    }


class TestRunDiscoveryAsync:
    """Unit tests for _run_discovery_async (all I/O mocked)."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _build_mocks(
        self,
        existing_rows=None,
        serpapi_results=None,
        lead_id_start=1,
    ):
        """Build a complete set of mocks for _run_discovery_async."""
        fake_config = _make_fake_config(["packaging company"])

        # Mock _load_existing_sets: returns (place_ids_set, domains_set)
        existing_place_ids = {r[0] for r in (existing_rows or []) if r[0]}
        existing_domains = set()

        # Mock _fetch_category_results
        results = serpapi_results or [_serpapi_result()]

        # Mock _insert_leads_batch: return sequential IDs
        new_ids = list(range(lead_id_start, lead_id_start + len(results)))

        return fake_config, existing_place_ids, existing_domains, results, new_ids

    def test_new_lead_inserted_and_enqueued(self):
        raw = _serpapi_result("pid1", "Acme Co", "https://acme.com")
        with (
            patch("iolabs_sdr.workers.discovery.load_client_config", return_value=_make_fake_config()),
            patch("iolabs_sdr.workers.discovery._get_serpapi_key", return_value="KEY"),
            patch("iolabs_sdr.workers.discovery._load_existing_sets", new_callable=AsyncMock, return_value=(set(), set())),
            patch("iolabs_sdr.workers.discovery._fetch_category_results", return_value=[raw]),
            patch("iolabs_sdr.workers.discovery._insert_leads_batch", new_callable=AsyncMock, return_value=[42]),
            patch("iolabs_sdr.workers.discovery._write_audit_log", new_callable=AsyncMock),
            patch("iolabs_sdr.workers.discovery.app.send_task") as mock_send,
        ):
            result = asyncio.run(_run_discovery_async("test_client"))

        assert result["new_leads"] == 1
        assert result["duplicates"] == 0
        assert result["errors"] == 0
        mock_send.assert_called_once_with(
            "iolabs_sdr.workers.classify.classify_lead",
            kwargs={"lead_id": 42, "client_id": "test_client"},
            queue="test_client_classify",
        )

    def test_duplicate_by_place_id_skipped(self):
        raw = _serpapi_result("pid1", "Acme Co")
        existing_ids = {"pid1"}
        with (
            patch("iolabs_sdr.workers.discovery.load_client_config", return_value=_make_fake_config()),
            patch("iolabs_sdr.workers.discovery._get_serpapi_key", return_value="KEY"),
            patch("iolabs_sdr.workers.discovery._load_existing_sets", new_callable=AsyncMock, return_value=(existing_ids, set())),
            patch("iolabs_sdr.workers.discovery._fetch_category_results", return_value=[raw]),
            patch("iolabs_sdr.workers.discovery._insert_leads_batch", new_callable=AsyncMock, return_value=[]) as mock_insert,
            patch("iolabs_sdr.workers.discovery._write_audit_log", new_callable=AsyncMock),
            patch("iolabs_sdr.workers.discovery.app.send_task") as mock_send,
        ):
            result = asyncio.run(_run_discovery_async("test_client"))

        assert result["new_leads"] == 0
        assert result["duplicates"] == 1
        mock_insert.assert_not_called()
        mock_send.assert_not_called()

    def test_duplicate_by_domain_skipped(self):
        raw = _serpapi_result("pid_new", "Acme Co", "https://acme.com")
        existing_domains = {"acme.com"}
        with (
            patch("iolabs_sdr.workers.discovery.load_client_config", return_value=_make_fake_config()),
            patch("iolabs_sdr.workers.discovery._get_serpapi_key", return_value="KEY"),
            patch("iolabs_sdr.workers.discovery._load_existing_sets", new_callable=AsyncMock, return_value=(set(), existing_domains)),
            patch("iolabs_sdr.workers.discovery._fetch_category_results", return_value=[raw]),
            patch("iolabs_sdr.workers.discovery._insert_leads_batch", new_callable=AsyncMock) as mock_insert,
            patch("iolabs_sdr.workers.discovery._write_audit_log", new_callable=AsyncMock),
            patch("iolabs_sdr.workers.discovery.app.send_task"),
        ):
            result = asyncio.run(_run_discovery_async("test_client"))

        assert result["duplicates"] == 1
        mock_insert.assert_not_called()

    def test_second_result_same_domain_in_same_run_is_deduped(self):
        """Within a single run, the same domain appearing twice should only produce 1 lead."""
        r1 = _serpapi_result("pid1", "Acme Co", "https://www.acme.com")
        r2 = _serpapi_result("pid2", "Acme Corp", "https://acme.com")  # same bare domain
        with (
            patch("iolabs_sdr.workers.discovery.load_client_config", return_value=_make_fake_config()),
            patch("iolabs_sdr.workers.discovery._get_serpapi_key", return_value="KEY"),
            patch("iolabs_sdr.workers.discovery._load_existing_sets", new_callable=AsyncMock, return_value=(set(), set())),
            patch("iolabs_sdr.workers.discovery._fetch_category_results", return_value=[r1, r2]),
            patch("iolabs_sdr.workers.discovery._insert_leads_batch", new_callable=AsyncMock, return_value=[1]) as mock_insert,
            patch("iolabs_sdr.workers.discovery._write_audit_log", new_callable=AsyncMock),
            patch("iolabs_sdr.workers.discovery.app.send_task"),
        ):
            result = asyncio.run(_run_discovery_async("test_client"))

        assert result["new_leads"] == 1
        assert result["duplicates"] == 1
        inserted = mock_insert.call_args[0][1]  # second positional arg is leads_data list
        assert len(inserted) == 1

    def test_serpapi_error_increments_errors_and_continues(self):
        """SerpAPI error for one category → errors++ but other categories still run."""
        config = _make_fake_config(["cat A", "cat B"])
        raw_b = _serpapi_result("pid_b", "Beta Co", "https://beta.com")
        with (
            patch("iolabs_sdr.workers.discovery.load_client_config", return_value=config),
            patch("iolabs_sdr.workers.discovery._get_serpapi_key", return_value="KEY"),
            patch("iolabs_sdr.workers.discovery._load_existing_sets", new_callable=AsyncMock, return_value=(set(), set())),
            patch(
                "iolabs_sdr.workers.discovery._fetch_category_results",
                side_effect=[SerpAPIError("network error"), [raw_b]],
            ),
            patch("iolabs_sdr.workers.discovery._insert_leads_batch", new_callable=AsyncMock, return_value=[99]),
            patch("iolabs_sdr.workers.discovery._write_audit_log", new_callable=AsyncMock),
            patch("iolabs_sdr.workers.discovery.app.send_task"),
        ):
            result = asyncio.run(_run_discovery_async("test_client"))

        assert result["errors"] == 1
        assert result["new_leads"] == 1

    def test_multiple_categories_combined(self):
        config = _make_fake_config(["cat A", "cat B"])
        r1 = _serpapi_result("pid1", "A Co", "https://a.com")
        r2 = _serpapi_result("pid2", "B Co", "https://b.com")
        with (
            patch("iolabs_sdr.workers.discovery.load_client_config", return_value=config),
            patch("iolabs_sdr.workers.discovery._get_serpapi_key", return_value="KEY"),
            patch("iolabs_sdr.workers.discovery._load_existing_sets", new_callable=AsyncMock, return_value=(set(), set())),
            patch("iolabs_sdr.workers.discovery._fetch_category_results", side_effect=[[r1], [r2]]),
            patch("iolabs_sdr.workers.discovery._insert_leads_batch", new_callable=AsyncMock, return_value=[1, 2]),
            patch("iolabs_sdr.workers.discovery._write_audit_log", new_callable=AsyncMock),
            patch("iolabs_sdr.workers.discovery.app.send_task") as mock_send,
        ):
            result = asyncio.run(_run_discovery_async("test_client"))

        assert result["new_leads"] == 2
        assert mock_send.call_count == 2

    def test_audit_log_written_at_end(self):
        with (
            patch("iolabs_sdr.workers.discovery.load_client_config", return_value=_make_fake_config()),
            patch("iolabs_sdr.workers.discovery._get_serpapi_key", return_value="KEY"),
            patch("iolabs_sdr.workers.discovery._load_existing_sets", new_callable=AsyncMock, return_value=(set(), set())),
            patch("iolabs_sdr.workers.discovery._fetch_category_results", return_value=[_serpapi_result()]),
            patch("iolabs_sdr.workers.discovery._insert_leads_batch", new_callable=AsyncMock, return_value=[1]),
            patch("iolabs_sdr.workers.discovery._write_audit_log", new_callable=AsyncMock) as mock_audit,
            patch("iolabs_sdr.workers.discovery.app.send_task"),
        ):
            asyncio.run(_run_discovery_async("test_client"))

        # Summary audit log must be written
        summary_call = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get("action") == "run_discovery"
        ]
        assert len(summary_call) == 1
        assert summary_call[0].kwargs["status"] == "success"

    def test_partial_error_audit_status(self):
        """When some categories fail, audit status should be 'partial_error'."""
        config = _make_fake_config(["cat A", "cat B"])
        with (
            patch("iolabs_sdr.workers.discovery.load_client_config", return_value=config),
            patch("iolabs_sdr.workers.discovery._get_serpapi_key", return_value="KEY"),
            patch("iolabs_sdr.workers.discovery._load_existing_sets", new_callable=AsyncMock, return_value=(set(), set())),
            patch(
                "iolabs_sdr.workers.discovery._fetch_category_results",
                side_effect=[SerpAPIError("fail"), []],
            ),
            patch("iolabs_sdr.workers.discovery._insert_leads_batch", new_callable=AsyncMock, return_value=[]),
            patch("iolabs_sdr.workers.discovery._write_audit_log", new_callable=AsyncMock) as mock_audit,
            patch("iolabs_sdr.workers.discovery.app.send_task"),
        ):
            asyncio.run(_run_discovery_async("test_client"))

        summary_call = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get("action") == "run_discovery"
        ]
        assert summary_call[0].kwargs["status"] == "partial_error"


# ── run_discovery Celery task ──────────────────────────────────────────────────


class TestRunDiscoveryCeleryTask:
    """Smoke tests for the Celery task wrapper (not the async logic)."""

    def test_returns_summary_on_success(self):
        expected = {"new_leads": 3, "duplicates": 1, "errors": 0}
        with patch(
            "iolabs_sdr.workers.discovery._run_discovery_async",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            from iolabs_sdr.workers.discovery import run_discovery

            result = run_discovery.run("acme")
        assert result == expected

    def test_unexpected_error_triggers_retry(self):
        """
        When an unexpected exception occurs, the task must not swallow it —
        it should propagate (Celery uses this to schedule a retry).
        When exc= is passed to self.retry(), Celery re-raises the original
        exception, so we assert the original RuntimeError propagates.
        """
        with patch(
            "iolabs_sdr.workers.discovery._run_discovery_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ):
            from iolabs_sdr.workers.discovery import run_discovery

            with pytest.raises(RuntimeError, match="db down"):
                run_discovery.run("acme")
