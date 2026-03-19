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

# TODO: Step 17 — implement send_linkedin_invites + poll_linkedin_inbox tasks
raise NotImplementedError("workers/linkedin.py: implemented in Step 17")
