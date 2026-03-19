"""
IOlabs AI SDR Platform — Celery Application (Step 4)

Queue naming convention: {client_id}_{stage}
  Stages: discovery | classify | enrich | email | reply | linkedin

Multi-tenant isolation guarantees:
  - Each client gets dedicated queues — one slow client cannot starve another
  - Rate limits are applied per-client in Redis
  - Worker concurrency can be tuned per stage independently

Docker workers listen on stage-level queues for all provisioned clients.
Queue lists are supplied via CELERY_QUEUES_{STAGE_UPPER} env vars.
These are populated by scripts/provision_client.py (Step 5).

Example env vars after provisioning two clients:
  CELERY_QUEUES_DISCOVERY=client_acme_discovery,client_beta_discovery
  CELERY_QUEUES_CLASSIFY=client_acme_classify,client_beta_classify
  ... etc.

Beat schedule:
  Platform-wide: Mirror Fish feedback analyzer — nightly at 02:00 UTC.
  Per-client: discovery cron + LinkedIn polling — registered by provision_client.py.
"""

from __future__ import annotations

import os
from typing import FrozenSet

from celery import Celery
from celery.schedules import crontab

# ── Constants ─────────────────────────────────────────────────────────────────

PIPELINE_STAGES: FrozenSet[str] = frozenset(
    {"discovery", "classify", "enrich", "email", "reply", "linkedin"}
)

# ── Celery app ─────────────────────────────────────────────────────────────────

app = Celery("iolabs_sdr")

app.conf.update(
    # Broker + backend
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),

    # Serialisation — JSON only, no pickle
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Reliability settings
    task_track_started=True,
    # Ack late: task is re-queued if worker dies before completing.
    # Email tasks guard against duplicates via "already sent?" check (BR1).
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # One task at a time per worker process — keeps rate limits accurate.
    worker_prefetch_multiplier=1,

    # Result expiry
    result_expires=3600,

    # Retry policy defaults (individual tasks override as needed)
    task_max_retries=3,
    task_default_retry_delay=60,
)

# ── Platform-wide Beat schedule ────────────────────────────────────────────────
# Per-client schedules (discovery cron, LinkedIn polling) are added dynamically
# by scripts/provision_client.py (Step 5).

app.conf.beat_schedule = {
    # Mirror Fish — nightly feedback analyzer (Section 14)
    "mirror_fish_feedback_nightly": {
        "task": "iolabs_sdr.mirror_fish.feedback_analyzer.run_nightly",
        "schedule": crontab(hour=2, minute=0),  # 02:00 UTC every day
        "kwargs": {},
    },
}

# Persistent Beat schedule stored in a Docker volume (see docker-compose.yml)
app.conf.beat_schedule_filename = os.environ.get(
    "CELERY_BEAT_SCHEDULE_FILE", "/var/celery/celerybeat-schedule"
)


# ── Queue naming utilities ─────────────────────────────────────────────────────


def get_queue_name(client_id: str, stage: str) -> str:
    """
    Return the Celery queue name for a given client and pipeline stage.

    Args:
        client_id: Client slug, e.g. "acme". Must be lowercase alphanumeric + underscores.
        stage:     Pipeline stage. Must be one of PIPELINE_STAGES.

    Returns:
        Queue name string, e.g. "client_acme_discovery".

    Raises:
        ValueError: If stage is not a valid pipeline stage.
    """
    if stage not in PIPELINE_STAGES:
        raise ValueError(
            f"Unknown pipeline stage '{stage}'. "
            f"Valid stages: {sorted(PIPELINE_STAGES)}"
        )
    return f"{client_id}_{stage}"


def get_all_client_queues(client_id: str) -> list[str]:
    """Return all 6 queue names for a given client (one per pipeline stage)."""
    return [get_queue_name(client_id, stage) for stage in sorted(PIPELINE_STAGES)]


def get_queues_for_stage(stage: str) -> list[str]:
    """
    Return all active client queues for a given stage.

    Reads the CELERY_QUEUES_{STAGE_UPPER} env var (comma-separated).
    Falls back to a single generic fallback queue if not set.

    Used by docker-compose worker commands to know which queues to consume.
    """
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Unknown stage '{stage}'")
    env_key = f"CELERY_QUEUES_{stage.upper()}"
    raw = os.environ.get(env_key, "")
    if raw.strip():
        return [q.strip() for q in raw.split(",") if q.strip()]
    # No clients provisioned yet — return a placeholder so the worker starts
    return [f"_unprovisioned_{stage}"]


# ── Per-client Beat schedule registration ─────────────────────────────────────


def register_client_beat_schedule(
    client_id: str,
    discovery_cron_hour: int = 7,
    discovery_cron_minute: int = 0,
    linkedin_poll_interval_minutes: int = 30,
) -> None:
    """
    Register per-client periodic tasks in the Beat schedule.

    Called by scripts/provision_client.py (Step 5) after a client is provisioned.
    Adds:
      1. Discovery cron — runs once daily at the specified time (default 07:00 UTC)
      2. LinkedIn inbox poll — runs every N minutes (default 30)

    Args:
        client_id: Client slug.
        discovery_cron_hour: UTC hour to run discovery cron (0–23).
        discovery_cron_minute: UTC minute offset (0–59).
        linkedin_poll_interval_minutes: LinkedIn inbox poll frequency in minutes.
    """
    discovery_key = f"discovery_cron_{client_id}"
    linkedin_key = f"linkedin_poll_{client_id}"

    app.conf.beat_schedule[discovery_key] = {
        "task": "iolabs_sdr.workers.discovery.run_discovery",
        "schedule": crontab(hour=discovery_cron_hour, minute=discovery_cron_minute),
        "kwargs": {"client_id": client_id},
        "options": {"queue": get_queue_name(client_id, "discovery")},
    }

    app.conf.beat_schedule[linkedin_key] = {
        "task": "iolabs_sdr.workers.linkedin.poll_linkedin_inbox",
        "schedule": crontab(minute=f"*/{linkedin_poll_interval_minutes}"),
        "kwargs": {"client_id": client_id},
        "options": {"queue": get_queue_name(client_id, "linkedin")},
    }
