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
  6. If tier == 'Discard': status='disqualified', STOP
  7. Else: enqueue discover_contacts → {client_id}_enrich

Business Rules:
  - Business Rule 8: screenshot failure → mark signal 'unresolvable', continue
  - Scraper timeout: retry once after 60s (Section 11)
  - Disqualifying signal fires → auto Discard regardless of score
"""

# TODO: Step 10 — implement classify_lead Celery task
raise NotImplementedError("workers/classify.py: implemented in Step 10")
