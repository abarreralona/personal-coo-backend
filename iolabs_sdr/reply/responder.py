"""
IOlabs AI SDR Platform — Reply Responder (Step 16)

Generates outbound replies for:
  INTERESTED     — LLM-generated reply using config.reply_handlers.interested.llm_prompt
  ASKING_FOR_INFO — Template reply from config.reply_handlers.asking_for_info.reply_template_html

Both require config.features.interested_reply_enabled = True to activate.

Business Rule 7:
  If LLM unavailable for INTERESTED reply → log degraded_mode, notify SDR immediately,
  do not send a broken reply. Human handoff.
"""

# TODO: Step 16 — implement Responder.generate_interested_reply() + generate_info_reply()
raise NotImplementedError("reply/responder.py: implemented in Step 16")
