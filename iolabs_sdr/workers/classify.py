"""
IOlabs AI SDR Platform — Stage 2: Lead Classification Worker (Step 10)

Queue: {client_id}_classify
Task:  classify_lead(lead_id, client_id)

Flow:
  1. Load lead + client config
  2. Screenshot scraper → homepage, logos_section, products screenshots
  3. Evaluate all signals via classifiers/signal_engine.py
  4. Score via classifiers/scorer.py → final_score + tier_label
  5. UPDATE lead: tier, classification_score, signals JSONB, status='classified'
  6. If tier == 'Discard': status='disqualified', STOP — do NOT enqueue Stage 3
  7. Else: enqueue discover_contacts → {client_id}_enrich

Business Rules:
  - BR8: screenshot failure → mark signal 'unresolvable', continue (don't skip lead)
  - Scraper timeout: retry once after 60s (Section 11)
  - disqualifying signal → auto Discard regardless of total score
"""

from __future__ import annotations


def classify_lead(lead_id: int, client_id: str) -> dict:
    """
    Celery task: classify a lead using screenshots + signal matrix.
    Implemented in Step 10.

    Returns {lead_id, tier, score, signals_evaluated, status}
    """
    # TODO: Step 10 — implement full classification pipeline
    raise NotImplementedError(
        "workers/classify.py: classify_lead() implemented in Step 10"
    )
