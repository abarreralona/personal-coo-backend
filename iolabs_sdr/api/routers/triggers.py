"""
IOlabs AI SDR Platform — Trigger Endpoints (Step 14)

Endpoints:
  POST /api/trigger/discovery — manually trigger Stage 1 discovery for a client
  GET  /api/health            — platform health check (PostgreSQL, Redis, Celery queues)
"""

from fastapi import APIRouter, Depends
from iolabs_sdr.api.dependencies import verify_api_key

router = APIRouter(prefix="/api", tags=["triggers"])


@router.post("/trigger/discovery")
async def trigger_discovery(
    client_id: str,
    _key: str = Depends(verify_api_key),
) -> dict:
    """
    Manually trigger Stage 1 Lead Discovery for a given client.
    Enqueues run_discovery task to {client_id}_discovery queue.
    Implemented fully in Step 14.
    """
    # TODO: Step 14 — validate client_id, enqueue workers.discovery.run_discovery
    return {"status": "queued", "client_id": client_id}


@router.get("/health")
async def health_check() -> dict:
    """
    Returns status of PostgreSQL, Redis, and all Celery queues.
    Implemented fully in Step 19.
    """
    # TODO: Step 19 — ping PostgreSQL, Redis, inspect Celery queue lengths
    return {
        "status": "ok",
        "postgres": "unchecked",
        "redis": "unchecked",
        "celery_queues": "unchecked",
    }
