"""
IOlabs AI SDR Platform — Signal Engine Orchestrator (Step 9)

Orchestrates evaluation of all signal types defined in config.classification_rules
for a given lead. Handles scraper failures gracefully per Business Rule 8.

Signal types:
  visual_ai        → classifiers/visual_classifier.py
  keyword          → classifiers/keyword_scanner.py
  llm_pickup       → classifiers/llm_pickup.py
  deterministic_rule → evaluated inline from structured lead data

Business Rule 8:
  If scraper fails for a signal source → mark signal as 'unresolvable',
  continue with remaining signals. Do NOT skip the lead.
"""

# TODO: Step 9 — implement SignalEngine.evaluate(lead, config) → List[SignalResult]
raise NotImplementedError("classifiers/signal_engine.py: implemented in Step 9")
