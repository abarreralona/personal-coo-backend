"""
IOlabs AI SDR Platform — Visual AI Classifier (Step 8)

Sends screenshots to Claude Vision model and parses confidence scores.

Confidence thresholds (Section 5, Stage 2):
  >= 0.75  → detected     → full weight applied
  0.50–0.74 → weak signal → half weight applied
  < 0.50   → not detected → zero weight

Model: config from ANTHROPIC_VISION_MODEL env var (defaults to claude-sonnet-4-20250514)
"""

# TODO: Step 8 — implement VisualClassifier.classify(screenshot_b64, prompt) → VisualResult
raise NotImplementedError("classifiers/visual_classifier.py: implemented in Step 8")
