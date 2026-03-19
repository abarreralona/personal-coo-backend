"""
IOlabs AI SDR Platform — Admin Endpoints (Step 14)

Endpoints:
  GET  /api/clients           — list all active tenants
  GET  /api/clients/{id}/status — per-client pipeline status
"""

from fastapi import APIRouter, Depends
from iolabs_sdr.api.dependencies import verify_api_key

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/clients")
async def list_clients(_key: str = Depends(verify_api_key)) -> dict:
    """
    Returns all active tenants from platform.tenants.
    Implemented fully in Step 14.
    """
    # TODO: Step 14 — query platform.tenants WHERE active = TRUE
    return {"clients": []}


@router.get("/clients/{client_id}/status")
async def client_status(
    client_id: str,
    _key: str = Depends(verify_api_key),
) -> dict:
    """
    Returns pipeline metrics for a specific client:
    leads discovered, classified, enriched; emails sent today; reply counts.
    Implemented fully in Step 14.
    """
    # TODO: Step 14 — aggregate per-client stats from client_{id} schema tables
    return {"client_id": client_id, "status": "not_implemented"}
