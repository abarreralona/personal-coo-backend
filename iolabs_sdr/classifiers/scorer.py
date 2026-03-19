"""
IOlabs AI SDR Platform — Classification Scorer (Step 7)

Applies weighted signal results to compute final_score and tier_label.

Rules (non-negotiable):
  1. Any signal with disqualifying=True and detected=True → tier='Discard', score=0 IMMEDIATELY
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

# TODO: Step 7 — implement Scorer.score(signal_results, config) → ScoreResult
raise NotImplementedError("classifiers/scorer.py: implemented in Step 7")
