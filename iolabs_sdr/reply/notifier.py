"""
IOlabs AI SDR Platform — SDR Handoff Notifier (Step 16)

Sends handoff notifications when a contact reaches:
  INTERESTED       — notify SDR via config.notification_channels
  COMPLEX_QUESTION — notify SDR + pause ALL automation for contact

Notification channels (per config.notification_channels):
  slack_webhook_url  → POST JSON payload to Slack incoming webhook
  alert_email        → send email via platform SMTP
  custom_webhook_url → POST to arbitrary webhook endpoint

TODO: OPEN ITEM 6 — Define exact fields required in SDR handoff notification payload.
  Minimum required for SDR to act immediately without opening the system.
  Fields currently expected: contact name, company, email, reply text, thread URL,
  sequence stage, classification type. CONFIRM WITH IOLABS OPERATOR.
"""

# TODO: Step 16 — implement Notifier.send_handoff(contact, reply_classification, client_config)
raise NotImplementedError("reply/notifier.py: implemented in Step 16")
