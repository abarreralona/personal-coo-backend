"""
IOlabs AI SDR Platform — 7-State Reply Classifier (Step 15)

CRITICAL — Business Rule 6:
  Deterministic checks MUST run before any LLM call.
  This is enforced STRUCTURALLY: the code path for deterministic checks
  returns early and never reaches the LLM branch if a match is found.
  A comment alone is NOT sufficient enforcement.

Classification pipeline (Section 6):
  receive_reply(text)
    → strip_quoted_thread(text)       # remove everything below 'On ... wrote:'
    → run_deterministic_checks(text)  # ALWAYS FIRST — structural enforcement
        → match? → return ReplyClassification immediately
        → no match? → run_llm_classifier(text)
            → classify into exactly one of 7 states
            → return ReplyClassification

7 States:
  OUT_OF_OFFICE    — deterministic first; extract return_date via LLM for scheduling
  NOT_INTERESTED   — deterministic; pause 90 days, do NOT add to DNC
  UNSUBSCRIBE      — deterministic; INSERT dnc_list, cancel ALL pending tasks (BR4)
  WRONG_EMAIL      — deterministic (5xx bounce wins over OOO body content)
  INTERESTED       — LLM primary + keyword boost; auto-reply + SDR notify + pause
  ASKING_FOR_INFO  — LLM; auto-reply from template; continue sequence
  COMPLEX_QUESTION — LLM; handoff notification + pause ALL automation

Edge cases (Section 6 + Section 11):
  - OOO with enthusiastic language → OOO wins (deterministic fires first)
  - 5xx SMTP bounce with OOO body → WRONG_EMAIL wins (deterministic fires first)
  - "ok" / single word → ASKING_FOR_INFO (do not assume INTERESTED)
  - Non-English → detect, proceed if LLM capable, else COMPLEX_QUESTION
  - Thread reply → strip quoted content before ANY classification

LLM prompt for classification:
  Classify this reply into exactly one of:
  OUT_OF_OFFICE, NOT_INTERESTED, UNSUBSCRIBE, WRONG_EMAIL, INTERESTED,
  ASKING_FOR_INFO, COMPLEX_QUESTION.
  Return JSON: {type, confidence, reasoning}

Acceptance: All 20 fixture replies in tests/fixtures/replies/ must classify correctly.
"""

# TODO: Step 15 — implement ReplyDetector with:
#   strip_quoted_thread(text) → str
#   classify(text, client_config) → ReplyClassification
#   _run_deterministic(text) → ReplyClassification | None  (MUST run first)
#   _run_llm_classifier(text, client_config) → ReplyClassification
raise NotImplementedError("reply/detector.py: implemented in Step 15")
