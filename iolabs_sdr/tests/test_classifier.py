"""
IOlabs AI SDR Platform — Classifier Tests (Steps 7–10)

Tests:
  - KeywordScanner: case-insensitive match, multiple keywords, no false positives
  - Scorer: disqualifying signal → auto Discard regardless of other signals
  - Scorer: visual_ai confidence thresholds (>= 0.75, 0.50–0.74, < 0.50)
  - Scorer: unresolvable signal contributes zero weight (not penalized)
  - Scorer: tier thresholds A/B/C correctly mapped from final_score
  - SignalEngine: scraper failure → signal marked unresolvable, pipeline continues
  - VisualClassifier: confidence parsing from Claude response
  - LLMPickup: LLM unavailable → log degraded_mode, mark unresolvable
"""

import pytest

from iolabs_sdr.classifiers.keyword_scanner import KeywordResult, KeywordScanner
from iolabs_sdr.classifiers.scorer import ScoreResult, Scorer, SignalResult


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_tiers(a_min=70.0, b_min=40.0, c_min=0.0):
    """Build a ClassificationTiers-like object using MagicMock-style duck typing."""
    from unittest.mock import MagicMock

    tiers = MagicMock()
    tiers.A.min_score = a_min
    tiers.A.label = "Hot"
    tiers.B.min_score = b_min
    tiers.B.label = "Warm"
    tiers.C.min_score = c_min
    tiers.C.label = "Discard"
    return tiers


def _signal(
    rule_name="test_rule",
    signal_type="keyword",
    detected=True,
    confidence=None,
    weight=25.0,
    disqualifying=False,
    unresolvable=False,
) -> SignalResult:
    return SignalResult(
        rule_name=rule_name,
        signal_type=signal_type,
        detected=detected,
        confidence=confidence,
        weight=weight,
        disqualifying=disqualifying,
        unresolvable=unresolvable,
    )


# ══════════════════════════════════════════════════════════════════════════════
# KEYWORD SCANNER (Step 7)
# ══════════════════════════════════════════════════════════════════════════════


def test_keyword_scanner_case_insensitive():
    """Keyword match must be case-insensitive regardless of text or keyword casing."""
    result = KeywordScanner.scan(
        "This company offers Pharmaceutical Packaging solutions.",
        ["pharmaceutical packaging"],
    )
    assert result.detected is True
    assert result.count == 1
    assert "pharmaceutical packaging" in result.matched_keywords


def test_keyword_scanner_multiple_keywords_all_matched():
    text = "We specialize in pharmaceutical packaging, GMP facilities and cleanroom assembly."
    keywords = ["pharmaceutical packaging", "GMP", "cleanroom"]
    result = KeywordScanner.scan(text, keywords)
    assert result.detected is True
    assert result.count == 3
    assert set(result.matched_keywords) == {"pharmaceutical packaging", "GMP", "cleanroom"}


def test_keyword_scanner_partial_match():
    text = "We do pharmaceutical packaging but not GMP."
    keywords = ["pharmaceutical packaging", "GMP", "cleanroom"]
    result = KeywordScanner.scan(text, keywords)
    assert result.count == 2
    assert "cleanroom" not in result.matched_keywords


def test_keyword_scanner_no_match_returns_detected_false():
    result = KeywordScanner.scan("Regular cardboard box company.", ["pharmaceutical"])
    assert result.detected is False
    assert result.count == 0
    assert result.matched_keywords == []


def test_keyword_scanner_empty_text_returns_no_match():
    result = KeywordScanner.scan("", ["pharma"])
    assert result.detected is False


def test_keyword_scanner_empty_keywords_returns_no_match():
    result = KeywordScanner.scan("pharma text", [])
    assert result.detected is False


def test_keyword_scanner_deduplicates_same_keyword():
    """Same keyword appearing twice in the keywords list → counted once."""
    result = KeywordScanner.scan("pharma packaging", ["pharma", "PHARMA"])
    assert result.count == 1


def test_keyword_scanner_no_false_positive():
    text = "We make cardboard boxes for retail."
    keywords = ["pharmaceutical", "blister pack", "FDA compliant"]
    result = KeywordScanner.scan(text, keywords)
    assert result.detected is False
    assert result.matched_keywords == []


def test_keyword_scanner_result_type():
    result = KeywordScanner.scan("pharma company", ["pharma"])
    assert isinstance(result, KeywordResult)
    assert isinstance(result.matched_keywords, list)
    assert isinstance(result.count, int)
    assert isinstance(result.detected, bool)


# ══════════════════════════════════════════════════════════════════════════════
# SCORER — Disqualifying signals (Step 7)
# ══════════════════════════════════════════════════════════════════════════════


def test_disqualifying_signal_forces_discard():
    """Score doesn't matter — disqualifying signal hit → tier=C always."""
    tiers = _make_tiers()
    signals = [
        _signal("big_positive", "keyword", detected=True, weight=100.0),
        _signal("disq_rule", "keyword", detected=True, weight=0.0, disqualifying=True),
    ]
    result = Scorer.score(signals, tiers)

    assert result.tier == "C"
    assert result.tier_label == "Discard"
    assert result.final_score == 0.0
    assert result.disqualified is True


def test_disqualifying_signal_not_fired_does_not_discard():
    """Disqualifying rule exists but detected=False → normal scoring continues."""
    tiers = _make_tiers()
    signals = [
        _signal("big_positive", "keyword", detected=True, weight=80.0),
        _signal("disq_rule", "keyword", detected=False, weight=0.0, disqualifying=True),
    ]
    result = Scorer.score(signals, tiers)
    assert result.tier == "A"
    assert result.disqualified is False


def test_disqualifying_trace_entry_has_discard_triggered_true():
    tiers = _make_tiers()
    signals = [_signal("bad_signal", "keyword", detected=True, disqualifying=True)]
    result = Scorer.score(signals, tiers)
    discard_entries = [t for t in result.signal_trace if t.discard_triggered]
    assert len(discard_entries) == 1
    assert discard_entries[0].rule_name == "bad_signal"


# ══════════════════════════════════════════════════════════════════════════════
# SCORER — Visual AI confidence thresholds (Step 7)
# ══════════════════════════════════════════════════════════════════════════════


def test_visual_ai_full_weight_above_75():
    """confidence >= 0.75 → full weight applied."""
    tiers = _make_tiers()
    signals = [_signal("logo_check", "visual_ai", detected=True, confidence=0.90, weight=25.0)]
    result = Scorer.score(signals, tiers)
    trace = result.signal_trace[0]
    assert trace.weight_applied == 25.0
    assert result.final_score == 25.0


def test_visual_ai_full_weight_at_exactly_75():
    tiers = _make_tiers()
    signals = [_signal("logo_check", "visual_ai", detected=True, confidence=0.75, weight=25.0)]
    result = Scorer.score(signals, tiers)
    assert result.signal_trace[0].weight_applied == 25.0


def test_visual_ai_half_weight_50_to_74():
    """0.50 <= confidence < 0.75 → half weight applied."""
    tiers = _make_tiers()
    signals = [_signal("logo_check", "visual_ai", detected=True, confidence=0.65, weight=20.0)]
    result = Scorer.score(signals, tiers)
    trace = result.signal_trace[0]
    assert trace.weight_applied == 10.0
    assert result.final_score == 10.0


def test_visual_ai_half_weight_at_exactly_50():
    tiers = _make_tiers()
    signals = [_signal("logo_check", "visual_ai", detected=True, confidence=0.50, weight=20.0)]
    result = Scorer.score(signals, tiers)
    assert result.signal_trace[0].weight_applied == 10.0


def test_visual_ai_zero_weight_below_50():
    """confidence < 0.50 → zero weight."""
    tiers = _make_tiers()
    signals = [_signal("logo_check", "visual_ai", detected=True, confidence=0.30, weight=25.0)]
    result = Scorer.score(signals, tiers)
    trace = result.signal_trace[0]
    assert trace.weight_applied == 0.0
    assert result.final_score == 0.0


def test_visual_ai_zero_confidence_is_zero_weight():
    tiers = _make_tiers()
    signals = [_signal("logo_check", "visual_ai", detected=True, confidence=0.0, weight=25.0)]
    result = Scorer.score(signals, tiers)
    assert result.signal_trace[0].weight_applied == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# SCORER — Unresolvable signals (Step 7)
# ══════════════════════════════════════════════════════════════════════════════


def test_unresolvable_signal_zero_contribution():
    """Unresolvable signal: zero contribution, total score not reduced."""
    tiers = _make_tiers()
    signals = [
        _signal("good_kw", "keyword", detected=True, weight=50.0),
        _signal("scraper_fail", "visual_ai", detected=None, weight=25.0, unresolvable=True),
    ]
    result = Scorer.score(signals, tiers)

    unresolvable_trace = next(t for t in result.signal_trace if t.unresolvable)
    assert unresolvable_trace.contribution == 0.0
    assert unresolvable_trace.weight_applied == 0.0
    # Score is from the good keyword only, not penalised for the scraper failure
    assert result.final_score == 50.0


def test_unresolvable_signal_does_not_penalise_tier():
    """An unresolvable signal should not drag the tier down."""
    tiers = _make_tiers()
    # Without the unresolvable signal, score = 75 → Tier A
    # The unresolvable signal has weight 100 but should contribute 0
    signals = [
        _signal("kw", "keyword", detected=True, weight=75.0),
        _signal("fail", "visual_ai", detected=None, weight=100.0, unresolvable=True),
    ]
    result = Scorer.score(signals, tiers)
    assert result.tier == "A"


# ══════════════════════════════════════════════════════════════════════════════
# SCORER — Tier threshold assignment (Step 7)
# ══════════════════════════════════════════════════════════════════════════════


def test_tier_a_assigned_at_minimum_a_score():
    tiers = _make_tiers(a_min=70, b_min=40, c_min=0)
    signals = [_signal(weight=70.0, detected=True)]
    result = Scorer.score(signals, tiers)
    assert result.tier == "A"
    assert result.tier_label == "Hot"


def test_tier_b_assigned_between_b_and_a():
    tiers = _make_tiers(a_min=70, b_min=40, c_min=0)
    signals = [_signal(weight=55.0, detected=True)]
    result = Scorer.score(signals, tiers)
    assert result.tier == "B"
    assert result.tier_label == "Warm"


def test_tier_c_assigned_below_b_threshold():
    tiers = _make_tiers(a_min=70, b_min=40, c_min=0)
    signals = [_signal(weight=30.0, detected=True)]
    result = Scorer.score(signals, tiers)
    assert result.tier == "C"
    assert result.tier_label == "Discard"


def test_zero_score_is_tier_c():
    tiers = _make_tiers()
    signals = [_signal(weight=50.0, detected=False)]
    result = Scorer.score(signals, tiers)
    assert result.tier == "C"
    assert result.final_score == 0.0


def test_score_result_type():
    tiers = _make_tiers()
    result = Scorer.score([_signal(detected=True, weight=50.0)], tiers)
    assert isinstance(result, ScoreResult)
    assert isinstance(result.signal_trace, list)


def test_empty_signals_returns_zero_tier_c():
    tiers = _make_tiers()
    result = Scorer.score([], tiers)
    assert result.tier == "C"
    assert result.final_score == 0.0
    assert result.signal_trace == []


# ══════════════════════════════════════════════════════════════════════════════
# SCORER — Keyword/LLM binary scoring
# ══════════════════════════════════════════════════════════════════════════════


def test_keyword_detected_true_full_weight():
    tiers = _make_tiers()
    signals = [_signal("kw", "keyword", detected=True, weight=30.0)]
    result = Scorer.score(signals, tiers)
    assert result.final_score == 30.0


def test_keyword_detected_false_zero_weight():
    tiers = _make_tiers()
    signals = [_signal("kw", "keyword", detected=False, weight=30.0)]
    result = Scorer.score(signals, tiers)
    assert result.final_score == 0.0


def test_llm_pickup_detected_true_full_weight():
    tiers = _make_tiers()
    signals = [_signal("llm_sig", "llm_pickup", detected=True, weight=25.0)]
    result = Scorer.score(signals, tiers)
    assert result.final_score == 25.0


def test_llm_pickup_detected_false_zero():
    tiers = _make_tiers()
    signals = [_signal("llm_sig", "llm_pickup", detected=False, weight=25.0)]
    result = Scorer.score(signals, tiers)
    assert result.final_score == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# SCORER — Signal trace completeness
# ══════════════════════════════════════════════════════════════════════════════


def test_signal_trace_has_entry_per_signal():
    tiers = _make_tiers()
    signals = [
        _signal("s1", weight=10.0, detected=True),
        _signal("s2", weight=20.0, detected=False),
        _signal("s3", weight=30.0, detected=None, unresolvable=True),
    ]
    result = Scorer.score(signals, tiers)
    assert len(result.signal_trace) == 3


def test_signal_trace_after_disqualify_includes_all_rules():
    """Even when a disqualifying signal fires, all rules appear in the trace."""
    tiers = _make_tiers()
    signals = [
        _signal("s1", weight=50.0, detected=True),
        _signal("disq", weight=0.0, detected=True, disqualifying=True),
        _signal("s3", weight=20.0, detected=True),
    ]
    result = Scorer.score(signals, tiers)
    assert len(result.signal_trace) == 3


def test_combined_real_world_scenario():
    """
    Simulate the client_example classification_rules:
      enterprise_logos_visible: visual_ai, weight=25, confidence=0.85 → full → 25
      pharmaceutical_packaging_focus: keyword, weight=30, detected=True → 30
      custom_packaging_solutions: visual_ai, weight=20, confidence=0.60 → half → 10
      ecommerce_only_disqualifier: keyword, weight=0, detected=False, disqualifying → no discard
      b2b_manufacturing_signals: llm_pickup, weight=25, detected=True → 25
    Total: 25 + 30 + 10 + 25 = 90 → Tier A
    """
    tiers = _make_tiers(a_min=70, b_min=40, c_min=0)
    signals = [
        _signal("enterprise_logos_visible", "visual_ai", detected=True, confidence=0.85, weight=25.0),
        _signal("pharmaceutical_packaging_focus", "keyword", detected=True, weight=30.0),
        _signal("custom_packaging_solutions", "visual_ai", detected=True, confidence=0.60, weight=20.0),
        _signal("ecommerce_only_disqualifier", "keyword", detected=False, weight=0.0, disqualifying=True),
        _signal("b2b_manufacturing_signals", "llm_pickup", detected=True, weight=25.0),
    ]
    result = Scorer.score(signals, tiers)
    assert result.final_score == pytest.approx(90.0)
    assert result.tier == "A"
    assert result.disqualified is False


# ══════════════════════════════════════════════════════════════════════════════
# STEPS 9+ — skipped stubs (implemented later)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.skip(reason="Implemented in Step 9")
def test_signal_engine_continues_on_scraper_failure():
    pass


@pytest.mark.skip(reason="Implemented in Step 9")
def test_llm_unavailable_marks_degraded_mode():
    pass
