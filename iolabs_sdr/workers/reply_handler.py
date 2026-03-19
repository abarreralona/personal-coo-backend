"""
IOlabs AI SDR Platform — Stage 5: Email Reply Handler Worker (Step 16)

Queue: {client_id}_reply
Task:  handle_email_reply(reply_data, client_id)

Flow:
  1. Extract NEW reply text — strip quoted thread (text above 'On ... wrote:')
  2. Run deterministic classifier FIRST (Business Rule 6 — structural enforcement)
  3. If no deterministic match → run LLM classifier
  4. Route to correct handler (reply/responder.py or reply/notifier.py)
  5. UPDATE contact.status
  6. INSERT into client_{id}.email_replies

Business Rule 4: On UNSUBSCRIBE/WRONG_EMAIL/NOT_INTERESTED/DNC:
  Celery revoke() all task IDs from sequence_schedule for this contact IMMEDIATELY.
"""

# TODO: Step 16 — implement handle_email_reply Celery task
raise NotImplementedError("workers/reply_handler.py: implemented in Step 16")
