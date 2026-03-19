"""
IOlabs AI SDR Platform — Webhook Endpoints (Stage 14)

Endpoints:
  GET  /webhook/pixel   — tracking pixel (records open event)
  GET  /webhook/click   — click tracking + redirect
  POST /webhook/reply   — inbound email reply handler
"""

from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import Response, RedirectResponse

router = APIRouter(prefix="/webhook", tags=["webhooks"])

# 1x1 transparent GIF bytes
_TRANSPARENT_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
    b"!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)


@router.get("/pixel")
async def tracking_pixel(
    cid: str = Query(..., description="Contact UUID"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Response:
    """
    Record an email open event.
    Returns a 1x1 transparent GIF so the email client renders nothing visible.
    Implemented fully in Step 14.
    """
    # TODO: Step 14 — record open event in emails_sent.opened_at for contact cid
    background_tasks.add_task(_record_open_event, cid)
    return Response(content=_TRANSPARENT_GIF, media_type="image/gif")


@router.get("/click")
async def tracking_click(
    cid: str = Query(..., description="Contact UUID"),
    url: str = Query(..., description="Destination URL to redirect to"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> RedirectResponse:
    """
    Record a click event and redirect to the target URL.
    Implemented fully in Step 14.
    """
    # TODO: Step 14 — record click event in emails_sent.clicked_at for contact cid
    background_tasks.add_task(_record_click_event, cid, url)
    return RedirectResponse(url=url, status_code=302)


@router.post("/reply")
async def inbound_reply(
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict:
    """
    Receive an inbound email reply from the email gateway.
    Enqueues reply_handler task to the {client_id}_reply Celery queue.
    Implemented fully in Step 14.
    """
    # TODO: Step 14 — parse reply_data, resolve client_id, enqueue handle_email_reply task
    return {"status": "queued"}


async def _record_open_event(cid: str) -> None:
    """Background task: write open event to DB."""
    # TODO: Step 14 — implement DB write
    pass


async def _record_click_event(cid: str, url: str) -> None:
    """Background task: write click event to DB."""
    # TODO: Step 14 — implement DB write
    pass
