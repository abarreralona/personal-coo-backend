"""
IOlabs AI SDR Platform — LinkedIn Workers (Step 17)

WF5 — Connection Requests:
  Queue: {client_id}_linkedin
  Task:  send_linkedin_invites(client_id)
  - Daily cron per client
  - Respects config.linkedin_config.daily_invite_limit
  - Records pending invites in client_{id}.contacts (linkedin_status)
  - Does NOT re-invite already-connected or pending contacts (Section 11)

WF7 — Inbox Monitor:
  Task:  poll_linkedin_inbox(client_id)
  - Runs every 30 minutes via Celery Beat
  - Reuses reply/detector.py (same 7-state classifier)
  - Stores in client_{id}.linkedin_messages

TODO: OPEN ITEM 4 — LinkedIn persona reply prompts not yet provided
"""

from __future__ import annotations


def send_linkedin_invites(client_id: str) -> dict:
    """
    Celery task: send daily LinkedIn connection requests for a client.
    Respects config.linkedin_config.daily_invite_limit.
    Does NOT re-invite already-connected or pending contacts.
    Implemented in Step 17.

    Returns {invites_sent: int, skipped: int, errors: int}
    """
    # TODO: Step 17 — implement send_linkedin_invites task
    raise NotImplementedError("workers/linkedin.py: send_linkedin_invites() implemented in Step 17")


def poll_linkedin_inbox(client_id: str) -> dict:
    """
    Celery task: poll LinkedIn inbox and classify new messages.
    Runs every 30 minutes via Celery Beat.
    Reuses reply/detector.py (same 7-state classifier).
    Implemented in Step 17.

    TODO: OPEN ITEM 4 — LinkedIn persona reply prompts not yet provided

    Returns {messages_processed: int, replies_classified: int}
    """
    # TODO: Step 17 + OPEN ITEM 4 — implement poll_linkedin_inbox task
    raise NotImplementedError("workers/linkedin.py: poll_linkedin_inbox() implemented in Step 17 (pending OPEN ITEM 4)")
