"""
IOlabs AI SDR Platform — Reply Detector Tests (Step 15)

CRITICAL ACCEPTANCE CRITERION:
  All 20 fixture replies in tests/fixtures/replies/ must classify correctly.
  Deterministic checks must verifiably run before LLM on every call (confirmed by log).

Fixture files (created in Step 15):
  replies/ooo_simple.txt
  replies/ooo_with_enthusiasm.txt        — must classify OOO, not INTERESTED
  replies/ooo_with_return_date.txt
  replies/not_interested_plain.txt
  replies/not_interested_keep_posted.txt — NOT_INTERESTED, no DNC, pause 90 days
  replies/unsubscribe_direct.txt
  replies/unsubscribe_informal.txt
  replies/wrong_email_5xx_bounce.txt     — WRONG_EMAIL wins over OOO body
  replies/wrong_email_nddr.txt
  replies/interested_explicit.txt
  replies/interested_question_plus.txt   — INTERESTED wins, acknowledge question
  replies/interested_short_yes.txt       — "yes" → ASKING_FOR_INFO (not INTERESTED)
  replies/interested_sounds_good.txt
  replies/asking_for_info_basic.txt
  replies/asking_for_info_price.txt
  replies/asking_for_info_ok.txt         — "ok" → ASKING_FOR_INFO
  replies/complex_technical.txt
  replies/complex_multi_part.txt
  replies/complex_pricing_discussion.txt
  replies/non_english_spanish.txt        — detect language, route to COMPLEX_QUESTION

Business Rule 6 enforced:
  Test verifies deterministic check runs first by:
    1. Passing OOO + enthusiastic text → confirming OOO result
    2. Passing 5xx bounce with OOO body → confirming WRONG_EMAIL result
    3. Checking audit log for 'deterministic_check_ran=true' before LLM call
"""

import pytest
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "replies"

# TODO: Step 15 — implement all 20 tests, one per fixture file


@pytest.mark.skip(reason="Implemented in Step 15 — fixture files created there")
def test_all_20_fixture_replies():
    pass


@pytest.mark.skip(reason="Implemented in Step 15")
def test_ooo_with_enthusiasm_classifies_as_ooo():
    """OOO + enthusiastic language → OOO. Deterministic fires first. Never INTERESTED."""
    pass


@pytest.mark.skip(reason="Implemented in Step 15")
def test_bounce_with_ooo_body_classifies_as_wrong_email():
    """5xx SMTP bounce → WRONG_EMAIL. OOO body content irrelevant."""
    pass


@pytest.mark.skip(reason="Implemented in Step 15")
def test_short_ok_reply_classifies_as_asking_for_info():
    """'ok' → ASKING_FOR_INFO. Never assume INTERESTED."""
    pass


@pytest.mark.skip(reason="Implemented in Step 15")
def test_not_interested_no_dnc():
    """NOT_INTERESTED → pause 90 days, do NOT add to DNC."""
    pass


@pytest.mark.skip(reason="Implemented in Step 15")
def test_deterministic_runs_before_llm_structural():
    """Verify via call order / log that no LLM call is made for deterministic matches."""
    pass
