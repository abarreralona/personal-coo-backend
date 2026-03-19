"""
IOlabs AI SDR Platform — Email Sender (Step 13)

Sends outbound emails via aiosmtplib using the client's own SMTP credentials.
All business rules enforced HERE at send time — not just at scheduling time.

Business Rules (hard constraints — no exceptions):
  BR1: DNC check at the moment of SMTP call.
       Check client_{id}.dnc_list AND platform.dnc_global.
       Raise DNCViolationError if found — never send.

  BR2: Daily send limit enforced via Redis atomic INCR.
       Key: daily_sent:{client_id}:{YYYY-MM-DD}
       If count >= config.emails_per_day → raise DailyLimitExceededError.

  BR3: Business hours 08:00–18:00 in config.target_timezone.
       Apply ±15 minute random offset to every send.
       If outside window → delay task to next window start.

  BR5: Max 3 SMTP retry attempts.
       After 3 failures → flag contact for review in audit_log.
       Do NOT continue retrying.

SMTP credentials:
  Host/port/username from config.sender_smtp.
  Password loaded from env var SMTP_PASSWORD_{CLIENT_ID_UPPER} (never from config JSON).
"""

# TODO: Step 13 — implement EmailSender.send(email_payload, contact, client_config) → SentResult
raise NotImplementedError("email/sender.py: implemented in Step 13")
