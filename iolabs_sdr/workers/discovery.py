"""
IOlabs AI SDR Platform — Stage 1: Lead Discovery Worker (Step 6)

Queue: {client_id}_discovery
Task:  run_discovery(client_id)

Flow:
  1. Load client config
  2. For each google_category in config.discovery.google_categories:
     - SerpAPI Google Maps: "{category} in {target_geo}"
     - Parse: name, address, phone, website, category, rating, review_count, place_id
     - Deduplicate by place_id OR website domain
     - INSERT new leads with status='raw'
  3. Enqueue classify_lead for each new lead
  4. Log run summary to platform.audit_log

Edge cases:
  - SerpAPI rate limit: exponential backoff 30s → 60s → 120s (Section 11)
  - Duplicate lead: silent skip + log (Section 11)
"""

# TODO: Step 6 — implement run_discovery Celery task
raise NotImplementedError("workers/discovery.py: implemented in Step 6")
