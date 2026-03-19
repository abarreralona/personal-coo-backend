"""
IOlabs AI SDR Platform — Classification Scorer (Step 7)

Applies weighted signal results to compute final_score and tier_label.

Rules (non-negotiable):
  1. Any signal with disqualifying=True and detected=True → tier='C', score=0 IMMEDIATELY
  2. visual_ai signals: confidence >= 0.75 → full weight, 0.50–0.74 → half, < 0.50 → zero
  3. keyword signals: any match → full weight, no match → zero
  4. llm_pickup signals: result=True → full weight, False → zero
  5. 'unresolvable' signals: weight contribution = zero (do not penalize)
  6. Final tier determined by config.classification_tiers min_score thresholds

Output:
  final_score: float
  tier: 'A' | 'B' | 'C'
  tier_label: 'Hot' | 'Warm' | 'Discard'
  signal_trace: List[SignalTrace]  — full audit trail stored in leads.signals JSONB
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from iolabs_sdr.core.config_loader import ClassificationTiers


# ── Data models ────────────────────────────────────────────────────────────────


class SignalResult(BaseModel):
    """
    Result for a single classification signal, produced by SignalEngine (Step 9).
    Passed as-is to Scorer.score().

    For visual_ai signals: confidence is a float 0.0–1.0.
    For keyword/llm_pickup signals: confidence is None.
    When the underlying data source was unavailable: unresolvable=True, detected=None.
    """

    rule_name: str
    signal_type: str         # visual_ai | keyword | llm_pickup | deterministic_rule
    detected: bool | None    # None when unresolvable
    confidence: float | None = None  # visual_ai only; 0.0–1.0
    weight: float            # from ClassificationRule.weight
    disqualifying: bool      # from ClassificationRule.disqualifying
    unresolvable: bool = False


class SignalTrace(BaseModel):
    """
    Audit trail entry for one signal — persisted in leads.signals JSONB.
    Enables post-hoc inspection of every scoring decision.
    """

    rule_name: str
    signal_type: str
    detected: bool | None
    confidence: float | None
    weight: float             # configured weight
    weight_applied: float     # actual weight used (full, half, or zero)
    contribution: float       # score points added by this signal
    disqualifying: bool
    unresolvable: bool
    discard_triggered: bool = False


class ScoreResult(BaseModel):
    """Final classification output for one lead."""

    final_score: float
    tier: str          # 'A', 'B', or 'C'
    tier_label: str    # 'Hot', 'Warm', or 'Discard'
    disqualified: bool  # True when a disqualifying signal fired
    signal_trace: list[SignalTrace]


# ── Scoring logic ──────────────────────────────────────────────────────────────


def _visual_ai_weight_multiplier(confidence: float | None) -> float:
    """
    Map visual_ai confidence to a weight multiplier.

    >= 0.75 → 1.0 (full weight)
    0.50 – 0.74 → 0.5 (half weight)
    < 0.50 → 0.0 (zero)
    None → 0.0 (treat same as unresolvable)
    """
    if confidence is None:
        return 0.0
    if confidence >= 0.75:
        return 1.0
    if confidence >= 0.50:
        return 0.5
    return 0.0


def _assign_tier(score: float, tiers: ClassificationTiers) -> tuple[str, str]:
    """
    Assign a tier letter and label from the config thresholds.

    Evaluates in descending order (A is highest), returns the first tier
    whose min_score the lead meets.

    Returns:
        (tier_letter, tier_label) e.g. ("A", "Hot")
    """
    tier_order = [("A", tiers.A), ("B", tiers.B), ("C", tiers.C)]
    for letter, tier_cfg in tier_order:
        if score >= tier_cfg.min_score:
            return letter, tier_cfg.label
    # Fallback — C should always have min_score=0, so this is unreachable in practice
    return "C", tiers.C.label


class Scorer:
    """
    Applies weighted signal results to produce a final classification score.

    Usage:
        result = Scorer.score(signal_results, config.classification_tiers)
    """

    @staticmethod
    def score(
        signal_results: list[SignalResult],
        tiers: ClassificationTiers,
    ) -> ScoreResult:
        """
        Compute final_score and tier from a list of evaluated signal results.

        Rules applied in order:
          1. Disqualifying check: if any signal is disqualifying AND detected,
             return immediately with score=0, tier=C.
          2. Visual AI: confidence-weighted (full / half / zero).
          3. Keyword / LLM pickup / deterministic_rule: binary (full or zero).
          4. Unresolvable signals: zero contribution (never penalised).
          5. Tier assigned from config thresholds.

        Args:
            signal_results: List of evaluated signals from SignalEngine.
            tiers:          ClassificationTiers from client config.

        Returns:
            ScoreResult with final_score, tier, tier_label, signal_trace.
        """
        trace: list[SignalTrace] = []
        total_score: float = 0.0

        # ── Pass 1: disqualifying check ────────────────────────────────────
        for sr in signal_results:
            if sr.disqualifying and sr.detected is True:
                # Build trace showing this signal triggered discard
                trace_entry = SignalTrace(
                    rule_name=sr.rule_name,
                    signal_type=sr.signal_type,
                    detected=sr.detected,
                    confidence=sr.confidence,
                    weight=sr.weight,
                    weight_applied=0.0,   # score is zeroed out
                    contribution=0.0,
                    disqualifying=sr.disqualifying,
                    unresolvable=sr.unresolvable,
                    discard_triggered=True,
                )
                # Add remaining signals with zero contribution for full audit trail
                remaining = [
                    SignalTrace(
                        rule_name=r.rule_name,
                        signal_type=r.signal_type,
                        detected=r.detected,
                        confidence=r.confidence,
                        weight=r.weight,
                        weight_applied=0.0,
                        contribution=0.0,
                        disqualifying=r.disqualifying,
                        unresolvable=r.unresolvable,
                    )
                    for r in signal_results
                    if r.rule_name != sr.rule_name
                ]
                return ScoreResult(
                    final_score=0.0,
                    tier="C",
                    tier_label=tiers.C.label,
                    disqualified=True,
                    signal_trace=[trace_entry] + remaining,
                )

        # ── Pass 2: weighted scoring ───────────────────────────────────────
        for sr in signal_results:
            if sr.unresolvable or sr.detected is None:
                # Unresolvable: zero contribution, do not penalise
                trace.append(
                    SignalTrace(
                        rule_name=sr.rule_name,
                        signal_type=sr.signal_type,
                        detected=None,
                        confidence=sr.confidence,
                        weight=sr.weight,
                        weight_applied=0.0,
                        contribution=0.0,
                        disqualifying=sr.disqualifying,
                        unresolvable=True,
                    )
                )
                continue

            # Calculate weight multiplier based on signal type
            if sr.signal_type == "visual_ai":
                multiplier = _visual_ai_weight_multiplier(sr.confidence)
            else:
                # keyword, llm_pickup, deterministic_rule: binary
                multiplier = 1.0 if sr.detected else 0.0

            weight_applied = sr.weight * multiplier
            total_score += weight_applied

            trace.append(
                SignalTrace(
                    rule_name=sr.rule_name,
                    signal_type=sr.signal_type,
                    detected=sr.detected,
                    confidence=sr.confidence,
                    weight=sr.weight,
                    weight_applied=weight_applied,
                    contribution=weight_applied,
                    disqualifying=sr.disqualifying,
                    unresolvable=False,
                )
            )

        # ── Pass 3: tier assignment ────────────────────────────────────────
        tier_letter, tier_label = _assign_tier(total_score, tiers)

        return ScoreResult(
            final_score=total_score,
            tier=tier_letter,
            tier_label=tier_label,
            disqualified=False,
            signal_trace=trace,
        )
