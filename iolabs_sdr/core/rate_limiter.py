"""
IOlabs AI SDR Platform — Redis-backed Rate Limiter (Step 4)

Enforces per-client daily send limits.

Business Rule 2:
  - Counter key: daily_sent:{client_id}:{YYYY-MM-DD}
  - Atomic Redis INCR — never double-count
  - Resets at midnight in config.target_timezone

Business Rule 3:
  - Sends only within 08:00–18:00 in config.target_timezone
  - ±15 minute random offset applied at send time
"""

# TODO: Step 4 — implement RateLimiter class with check_and_increment(),
#               get_daily_count(), reset_at_midnight()
raise NotImplementedError("core/rate_limiter.py: implemented in Step 4")
