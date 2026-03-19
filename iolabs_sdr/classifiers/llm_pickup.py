"""
IOlabs AI SDR Platform — LLM Pickup Classifier (Step 9)

Posts page text summary to Claude and asks a structured question.
Returns a boolean result + reasoning string.

Business Rule 7:
  If LLM API is unavailable → log degraded_mode=true to audit_log,
  mark signal as 'unresolvable' (same as scraper failure).
  Never fail silently.

Model: ANTHROPIC_MODEL env var
"""

# TODO: Step 9 — implement LLMPickup.classify(text, prompt) → LLMPickupResult
raise NotImplementedError("classifiers/llm_pickup.py: implemented in Step 9")
