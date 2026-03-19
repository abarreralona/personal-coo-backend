"""
IOlabs AI SDR Platform — Stage 4: Email Sequence Worker (Steps 12–13)

Queue: {client_id}_email
Tasks:
  send_email_1(contact_id, client_id)
  send_email_2(contact_id, client_id)
  send_email_3(contact_id, client_id)

Pre-send checks (Business Rules — all hard-blocked, no exceptions):
  BR1: DNC check at SMTP send time (not just at scheduling time)
  BR2: Daily limit via Redis atomic counter key daily_sent:{client_id}:{YYYY-MM-DD}
  BR3: Business hours 08:00–18:00 target_timezone ±15 min random offset
  BR4: Cancel all pending tasks on DNC/UNSUBSCRIBE/WRONG_EMAIL/NOT_INTERESTED
  BR5: Max 3 SMTP retries, then flag for review
  BR7: LLM failure → use fallback_opening, log degraded_mode=true

Follow-up skip rules:
  - Contact has replied (any state) → SKIP
  - Contact on DNC → SKIP + cancel all
  - contact.sequence_paused == True → SKIP

TODO: OPEN ITEM 3 — Email 2 and Email 3 templates not yet provided
"""

# TODO: Step 13 — implement send_email_1, send_email_2, send_email_3 Celery tasks
raise NotImplementedError("workers/email_sender.py: implemented in Steps 12-13")
