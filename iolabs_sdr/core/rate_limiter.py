"""
IOlabs AI SDR Platform — Redis-backed Rate Limiter (Step 4)

Enforces two hard send constraints (Business Rules 2 & 3):

Business Rule 2 — Daily email limit:
  Counter key: daily_sent:{client_id}:{YYYY-MM-DD}   (in config.target_timezone)
  Implemented as atomic Redis INCR.
  Key expires after 48 hours (auto-cleanup).
  Raises DailyLimitExceededError when count >= config.emails_per_day.

Business Rule 3 — Business hours only:
  Window: 08:00–18:00 in config.target_timezone.
  Random ±15 minute jitter applied to every send (looks human).
  Raises BusinessHoursViolationError when outside window.

Usage (from email/sender.py):

    from iolabs_sdr.core.rate_limiter import RateLimiter

    limiter = RateLimiter()
    limiter.assert_within_daily_limit(client_id, config.emails_per_day, config.target_timezone)
    limiter.assert_business_hours(config.target_timezone)
    delay = limiter.jitter_delay_seconds()   # ±15 min random offset

    # After successful send:
    # (already incremented atomically in assert_within_daily_limit)

Synchronous Redis client — safe to call from Celery task context.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import redis

from iolabs_sdr.core.exceptions import BusinessHoursViolationError, DailyLimitExceededError

# ── Constants ──────────────────────────────────────────────────────────────────

SEND_WINDOW_START_HOUR: int = 8   # 08:00 local time
SEND_WINDOW_END_HOUR: int = 18    # 18:00 local time (exclusive)
JITTER_MINUTES: int = 15          # ±15 minute random offset on every send
COUNTER_TTL_SECONDS: int = 48 * 3600  # key auto-expires after 48 h


# ── Redis client ───────────────────────────────────────────────────────────────

def _get_redis_client() -> redis.Redis:
    """Return a synchronous Redis client (connection pool cached on module load)."""
    return redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
        socket_connect_timeout=5,
    )


# Module-level client — reused across tasks in the same worker process.
_redis: redis.Redis = _get_redis_client()


# ── Key helpers ────────────────────────────────────────────────────────────────


def _daily_counter_key(client_id: str, tz: ZoneInfo) -> str:
    """
    Build the Redis key for today's send counter.
    Business Rule 2: key = daily_sent:{client_id}:{YYYY-MM-DD}
    The date component uses the client's target_timezone so the counter
    resets at midnight local time, not UTC midnight.
    """
    date_str = datetime.now(tz).strftime("%Y-%m-%d")
    return f"daily_sent:{client_id}:{date_str}"


# ── RateLimiter ────────────────────────────────────────────────────────────────


class RateLimiter:
    """
    Stateless helper — safe to instantiate per task or share across tasks.
    All state lives in Redis; no in-process state is kept.
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._r = redis_client or _redis

    # ── Business Rule 2: Daily limit ──────────────────────────────────────────

    def assert_within_daily_limit(
        self,
        client_id: str,
        emails_per_day: int,
        timezone_str: str,
    ) -> int:
        """
        Atomically check-and-increment the daily send counter.

        Must be called ONCE per email actually sent.
        If the limit is not exceeded, the counter is incremented and the new
        count is returned. If the limit IS exceeded, the counter is decremented
        back and DailyLimitExceededError is raised — no double-counting.

        Args:
            client_id:      Client slug.
            emails_per_day: Max emails allowed today (from config).
            timezone_str:   pytz/zoneinfo timezone string (from config.target_timezone).

        Returns:
            New daily send count (1-indexed: first send returns 1).

        Raises:
            DailyLimitExceededError: Limit already reached. Caller should delay to tomorrow.
        """
        tz = ZoneInfo(timezone_str)
        key = _daily_counter_key(client_id, tz)

        # Atomic increment — then check. This is race-condition safe.
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.expire(key, COUNTER_TTL_SECONDS)
        new_count, _ = pipe.execute()

        if new_count > emails_per_day:
            # Roll back: we won't be sending
            self._r.decr(key)
            midnight = self._next_midnight_local(tz)
            raise DailyLimitExceededError(
                f"Daily send limit reached for client '{client_id}': "
                f"{emails_per_day} emails already sent today. "
                f"Counter resets at midnight {timezone_str} "
                f"(approximately {int((midnight - datetime.now(tz)).total_seconds() / 3600)}h away). "
                "Task will be rescheduled."
            )

        return int(new_count)

    def get_daily_count(self, client_id: str, timezone_str: str) -> int:
        """Return the current daily send count for a client (0 if not started)."""
        tz = ZoneInfo(timezone_str)
        key = _daily_counter_key(client_id, tz)
        value = self._r.get(key)
        return int(value) if value else 0

    def reset_daily_count(self, client_id: str, timezone_str: str) -> None:
        """
        Delete today's counter key. Used in tests and emergency resets.
        Does NOT affect tomorrow's counter (different key).
        """
        tz = ZoneInfo(timezone_str)
        key = _daily_counter_key(client_id, tz)
        self._r.delete(key)

    # ── Business Rule 3: Business hours ───────────────────────────────────────

    def assert_business_hours(self, timezone_str: str) -> None:
        """
        Raise BusinessHoursViolationError if the current time is outside
        the send window (08:00–18:00 in config.target_timezone).

        The caller (email/sender.py) should catch this and reschedule the
        task to the start of the next window.

        Raises:
            BusinessHoursViolationError: Current time is outside 08:00–18:00.
        """
        tz = ZoneInfo(timezone_str)
        now = datetime.now(tz)
        if not (SEND_WINDOW_START_HOUR <= now.hour < SEND_WINDOW_END_HOUR):
            next_window = self.seconds_until_window_open(timezone_str)
            raise BusinessHoursViolationError(
                f"Outside business hours in {timezone_str}: "
                f"current time is {now.strftime('%H:%M')}. "
                f"Send window is {SEND_WINDOW_START_HOUR:02d}:00–{SEND_WINDOW_END_HOUR:02d}:00. "
                f"Task will be rescheduled in ~{next_window // 60} minutes."
            )

    def is_business_hours(self, timezone_str: str) -> bool:
        """Return True if the current time is within the send window."""
        tz = ZoneInfo(timezone_str)
        now = datetime.now(tz)
        return SEND_WINDOW_START_HOUR <= now.hour < SEND_WINDOW_END_HOUR

    def seconds_until_window_open(self, timezone_str: str) -> int:
        """
        Return seconds until the next 08:00 send window opens (in local timezone).
        Adds no jitter — used for task rescheduling delay calculations.
        """
        tz = ZoneInfo(timezone_str)
        now = datetime.now(tz)
        next_open = now.replace(
            hour=SEND_WINDOW_START_HOUR, minute=0, second=0, microsecond=0
        )
        if now.hour >= SEND_WINDOW_START_HOUR:
            # Already past 08:00 today — next window is tomorrow
            next_open += timedelta(days=1)
        return max(0, int((next_open - now).total_seconds()))

    def seconds_until_window_close(self, timezone_str: str) -> int:
        """Return seconds until the send window closes at 18:00 (local timezone)."""
        tz = ZoneInfo(timezone_str)
        now = datetime.now(tz)
        close = now.replace(
            hour=SEND_WINDOW_END_HOUR, minute=0, second=0, microsecond=0
        )
        if now >= close:
            return 0
        return int((close - now).total_seconds())

    # ── Business Rule 3: Jitter ───────────────────────────────────────────────

    def jitter_delay_seconds(self) -> int:
        """
        Return a random offset in seconds, uniformly distributed over
        ±JITTER_MINUTES (±15 minutes).

        Applied to every outbound send to make email timing look human.
        The caller must clamp the final send time to remain within the window.
        """
        return random.randint(-JITTER_MINUTES * 60, JITTER_MINUTES * 60)

    def jitter_delay_positive_seconds(self) -> int:
        """
        Return a positive random delay in seconds (0 to JITTER_MINUTES).
        Used when scheduling the first email of the day (can't go negative
        before the window opens).
        """
        return random.randint(0, JITTER_MINUTES * 60)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _next_midnight_local(tz: ZoneInfo) -> datetime:
        """Return the next midnight in the given timezone."""
        now = datetime.now(tz)
        return (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    def ping(self) -> bool:
        """Return True if Redis is reachable. Used by /api/health endpoint."""
        try:
            return self._r.ping()
        except Exception:
            return False
