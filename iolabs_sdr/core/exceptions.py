"""
IOlabs AI SDR Platform — Custom Exception Classes

All platform exceptions inherit from IOLabsError so they can be caught
uniformly at task boundaries and logged to platform.audit_log.
"""


class IOLabsError(Exception):
    """Base exception for all IOlabs platform errors."""


# ── Config ────────────────────────────────────────────────────────────────────


class ConfigNotFoundError(IOLabsError):
    """Raised when a client config file cannot be located."""


class ConfigValidationError(IOLabsError):
    """Raised when a client config fails Pydantic validation."""


# ── Tenant / DB ───────────────────────────────────────────────────────────────


class TenantNotFoundError(IOLabsError):
    """Raised when a client_id is not registered in platform.tenants."""


class SchemaNotProvisionedError(IOLabsError):
    """Raised when the per-client DB schema does not exist."""


# ── Pipeline ──────────────────────────────────────────────────────────────────


class DNCViolationError(IOLabsError):
    """
    Raised when an email send is attempted to an address on the DNC list.
    Business Rule 1: DNC check at send time — never allow this to pass silently.
    """


class DailyLimitExceededError(IOLabsError):
    """
    Raised when the daily send counter for a client has reached its limit.
    Business Rule 2: enforced via Redis atomic increment.
    """


class BusinessHoursViolationError(IOLabsError):
    """
    Raised when a send is attempted outside 08:00–18:00 target timezone.
    Business Rule 3.
    """


class SequenceCancelledError(IOLabsError):
    """
    Raised when a sequence task fires but the contact has been cancelled
    (DNC, UNSUBSCRIBE, WRONG_EMAIL, NOT_INTERESTED).
    Business Rule 4.
    """


# ── External Services ─────────────────────────────────────────────────────────


class ScraperError(IOLabsError):
    """Raised when the screenshot scraper HTTP API fails or times out."""


class SerpAPIError(IOLabsError):
    """Raised when a SerpAPI call fails."""


class SerpAPIRateLimitError(SerpAPIError):
    """
    Raised on HTTP 429 from SerpAPI.
    Edge Case: trigger exponential backoff 30s → 60s → 120s.
    """


class LLMError(IOLabsError):
    """Raised when an Anthropic API call fails."""


class LLMUnavailableError(LLMError):
    """
    Raised when the LLM API is completely unreachable.
    Business Rule 7: trigger fallback_mode, log degraded_mode=true.
    """


class SMTPError(IOLabsError):
    """Raised on SMTP send failure."""


class SMTPMaxRetriesError(SMTPError):
    """
    Raised after 3 consecutive SMTP failures for a contact.
    Business Rule 5: flag contact for review, stop retrying.
    """
