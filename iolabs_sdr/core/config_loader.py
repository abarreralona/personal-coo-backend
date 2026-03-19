"""
IOlabs AI SDR Platform — Client Configuration Loader (Step 2)

Loads and validates per-client JSON config files using Pydantic v2 models.
Every client behavior is governed by these configs — nothing client-specific
is hardcoded anywhere else in the platform (Section 4 primary directive).

SMTP password is resolved from an environment variable at load time.
The JSON config stores a reference like ${SMTP_PASSWORD_CLIENT_EXAMPLE}.
The actual password is NEVER stored in the config file.

Usage:
    from core.config_loader import load_client_config
    config = load_client_config("acme")

Open Items flagged in configs (Section 16):
    Personas ops/finance/purchase/owner/development — templates pending OPEN ITEM 3
    LinkedInConfig.reply_prompt — pending OPEN ITEM 4
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.exceptions import ConfigNotFoundError, ConfigValidationError

# ── Constants ─────────────────────────────────────────────────────────────────

# Pattern for env var references in config values: ${SOME_VAR_NAME}
_ENV_REF_RE = re.compile(r"^\$\{([A-Z0-9_]+)\}$")

# Default configs directory (relative to project root)
CONFIGS_DIR = Path(__file__).parent.parent / "configs"

# All 6 persona types that must be present in every client config
REQUIRED_PERSONAS = frozenset({"executive", "ops", "finance", "purchase", "owner", "development"})


# ── Env var resolution ─────────────────────────────────────────────────────────


def resolve_env_ref(value: str, field_name: str, required: bool = True) -> str:
    """
    Resolve an environment variable reference like ${VAR_NAME}.

    If the value matches the ${VAR_NAME} pattern, the env var is looked up.
    If value is not a reference pattern, it is returned unchanged.

    Args:
        value:      The config value, which may be an env ref or a literal.
        field_name: Used in error messages to identify which field failed.
        required:   If True and the env var is not set, raises ConfigValidationError.

    Returns:
        Resolved string value.

    Raises:
        ConfigValidationError: If required=True and the env var is not set.
    """
    match = _ENV_REF_RE.match(value)
    if not match:
        return value  # literal value, use as-is
    env_var = match.group(1)
    resolved = os.environ.get(env_var)
    if resolved is None:
        if required:
            raise ConfigValidationError(
                f"Environment variable '{env_var}' (referenced by '{field_name}') is not set. "
                f"Add {env_var}=<value> to your .env file before starting the platform."
            )
        return value  # return unresolved reference for optional fields
    return resolved


# ── Sub-models ─────────────────────────────────────────────────────────────────


class SMTPConfig(BaseModel):
    """Client's own SMTP credentials for outbound email sends."""

    model_config = ConfigDict(extra="ignore")

    host: str = Field(..., min_length=1, description="SMTP server hostname")
    port: int = Field(587, ge=1, le=65535, description="SMTP port (usually 587 or 465)")
    username: str = Field(..., min_length=1, description="SMTP login username")
    password: str = Field(
        ...,
        description="Must be an env var reference: ${VAR_NAME}. Never store plain text here.",
    )

    @field_validator("password", mode="after")
    @classmethod
    def resolve_smtp_password(cls, v: str) -> str:
        """Resolve ${VAR} reference. Raises if env var is not set."""
        return resolve_env_ref(v, "sender_smtp.password", required=True)


class DiscoveryConfig(BaseModel):
    """Stage 1 Lead Discovery configuration."""

    model_config = ConfigDict(extra="ignore")

    google_categories: List[str] = Field(
        ...,
        min_length=1,
        description="Google Maps category strings to search for",
    )
    target_geo: str = Field(
        ...,
        min_length=1,
        description="Geographic scope, e.g. 'Texas, USA'",
    )


class ClassificationRule(BaseModel):
    """
    A single signal in the classification matrix.

    Signal types:
        visual_ai         — Claude Vision analyzes a screenshot
        keyword           — deterministic keyword match on scraped text
        llm_pickup        — Claude text model evaluates page content
        deterministic_rule — evaluated directly from structured lead data
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    type: Literal["visual_ai", "keyword", "llm_pickup", "deterministic_rule"]
    source: Literal[
        "homepage_screenshot",
        "logos_section_screenshot",
        "products_screenshot",
        "page_text",
        "structured_data",
    ]
    prompt: str = Field(default="", description="Required for visual_ai and llm_pickup types")
    keywords: List[str] = Field(default_factory=list, description="Required for keyword type")
    weight: float = Field(..., ge=0, le=100, description="Score contribution 0–100")
    disqualifying: bool = Field(
        False,
        description="If True and signal fires, lead is auto-discarded regardless of score",
    )

    @model_validator(mode="after")
    def validate_type_specific_requirements(self) -> ClassificationRule:
        if self.type in ("visual_ai", "llm_pickup") and not self.prompt:
            raise ValueError(
                f"Classification rule '{self.name}': type='{self.type}' requires a non-empty 'prompt'."
            )
        if self.type == "keyword" and not self.keywords:
            raise ValueError(
                f"Classification rule '{self.name}': type='keyword' requires at least one entry in 'keywords'."
            )
        return self


class TierConfig(BaseModel):
    """Score threshold and label for a single classification tier."""

    model_config = ConfigDict(extra="ignore")

    min_score: float = Field(..., ge=0, le=100)
    label: str = Field(..., min_length=1)


class ClassificationTiers(BaseModel):
    """
    A, B, C tier definitions. All three are mandatory.
    min_score must satisfy: A > B >= C.
    """

    model_config = ConfigDict(extra="ignore")

    A: TierConfig
    B: TierConfig
    C: TierConfig

    @model_validator(mode="after")
    def validate_tier_ordering(self) -> ClassificationTiers:
        if not (self.A.min_score > self.B.min_score >= self.C.min_score):
            raise ValueError(
                "Classification tiers must have strictly decreasing min_score thresholds: "
                f"A ({self.A.min_score}) must be > B ({self.B.min_score}) must be >= C ({self.C.min_score})."
            )
        return self


class SequenceTiming(BaseModel):
    """Days between emails in the sequence."""

    model_config = ConfigDict(extra="ignore")

    email_1_to_2: int = Field(..., gt=0, description="Days between Email 1 and Email 2")
    email_2_to_3: int = Field(..., gt=0, description="Days between Email 2 and Email 3")
    email_3_to_final: int = Field(..., gt=0, description="Days between Email 3 and final follow-up")


class PersonaConfig(BaseModel):
    """
    Configuration for a single buyer persona type.

    Required persona types: executive, ops, finance, purchase, owner, development.

    TODO: OPEN ITEM 3 — Email 2 and Email 3 template HTML for each persona
    are pending delivery from IOlabs operator. email_body_html currently
    covers Email 1 only.
    """

    model_config = ConfigDict(extra="ignore")

    system_prompt: str = Field(
        ...,
        min_length=1,
        description="Claude system prompt for opening paragraph generation",
    )
    fallback_opening: str = Field(
        ...,
        min_length=1,
        description="Used when LLM is unavailable (Business Rule 7)",
    )
    email_subject: str = Field(..., min_length=1, description="Subject line; may include {company_name}")
    email_body_html: str = Field(
        ...,
        min_length=1,
        description="Full HTML template with placeholders: {opening_paragraph}, {company_name}, etc.",
    )
    sequence_timing: SequenceTiming


class ReplyHandlerOOO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: Literal["reschedule"]


class ReplyHandlerNotInterested(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: Literal["flag_pause"]


class ReplyHandlerUnsubscribe(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: Literal["dnc"]


class ReplyHandlerWrongEmail(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: Literal["flag_invalid"]


class ReplyHandlerInterested(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    llm_prompt: str = Field(..., min_length=1, description="System prompt for generating the interested reply")


class ReplyHandlerAskingForInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    reply_template_html: str = Field(..., min_length=1, description="HTML template for info reply")


class ReplyHandlerComplexQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    handoff_channel: Literal["slack", "email", "webhook"]


class ReplyHandlers(BaseModel):
    """
    Reply routing config for all 7 reply states.
    All 7 handlers must be defined — none are optional.
    """

    model_config = ConfigDict(extra="ignore")

    ooo: ReplyHandlerOOO
    not_interested: ReplyHandlerNotInterested
    unsubscribe: ReplyHandlerUnsubscribe
    wrong_email: ReplyHandlerWrongEmail
    interested: ReplyHandlerInterested
    asking_for_info: ReplyHandlerAskingForInfo
    complex_question: ReplyHandlerComplexQuestion


class NotificationChannels(BaseModel):
    """Channels used by reply/notifier.py for SDR handoff alerts."""

    model_config = ConfigDict(extra="ignore")

    slack_webhook_url: Optional[str] = None
    alert_email: Optional[str] = None
    custom_webhook_url: Optional[str] = None


class LinkedInConfig(BaseModel):
    """
    LinkedIn outreach configuration (WF5 + WF7).

    TODO: OPEN ITEM 4 — reply_prompt is pending from IOlabs operator.
    """

    model_config = ConfigDict(extra="ignore")

    daily_invite_limit: int = Field(..., gt=0, le=50, description="Max connection requests per day")
    connection_message_template: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Max 300 chars; placeholders: {first_name}, {company_name}, {region}",
    )
    reply_prompt: str = Field(
        ...,
        min_length=1,
        description="TODO: OPEN ITEM 4 — LinkedIn reply generation system prompt",
    )


class Features(BaseModel):
    """Feature flags — all default to enabled. Override per client."""

    model_config = ConfigDict(extra="ignore")

    interested_reply_enabled: bool = True
    complex_handoff_enabled: bool = True
    linkedin_enabled: bool = True
    open_claw_enabled: bool = True
    mirror_fish_industry: str = Field(
        ...,
        min_length=1,
        description="Industry key for Mirror Fish seed file lookup",
    )


# ── Root config model ──────────────────────────────────────────────────────────


class ClientConfig(BaseModel):
    """
    Complete validated configuration for one client.
    Loaded from configs/{client_id}.json.

    All client-specific behavior flows from this model — nothing is hardcoded
    elsewhere in the platform (Section 4 primary directive).
    """

    model_config = ConfigDict(extra="ignore")

    client_id: str = Field(
        ...,
        min_length=1,
        description="Unique slug. Becomes PostgreSQL schema prefix and Celery queue prefix.",
    )
    sender_name: str = Field(..., min_length=1, description="Full name emails appear from")
    sender_email: str = Field(..., min_length=1, description="From address for outbound emails")
    sender_smtp: SMTPConfig

    emails_per_day: int = Field(
        ...,
        gt=0,
        le=500,
        description="Daily email send cap (Business Rule 2). Enforced via Redis.",
    )
    target_timezone: str = Field(..., min_length=1, description="pytz timezone string, e.g. 'America/Chicago'")
    blog_url: str = Field(..., min_length=1, description="Base URL for tracked blog link in Email 1")
    webhook_base_url: str = Field(..., min_length=1, description="Base URL for pixel/click/reply webhooks")

    discovery: DiscoveryConfig
    classification_rules: List[ClassificationRule] = Field(..., min_length=1)
    classification_tiers: ClassificationTiers

    personas: dict[str, PersonaConfig] = Field(
        ...,
        description="Must contain all 6 persona types: executive, ops, finance, purchase, owner, development",
    )

    reply_handlers: ReplyHandlers
    notification_channels: NotificationChannels
    handoff_trigger: List[str] = Field(..., min_length=1)
    linkedin_config: LinkedInConfig
    features: Features

    @field_validator("client_id", mode="after")
    @classmethod
    def validate_client_id_characters(cls, v: str) -> str:
        """
        client_id is used directly in PostgreSQL schema names and Celery queue names.
        Must be lowercase alphanumeric + underscores only — no hyphens, spaces, or special chars.
        """
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError(
                f"client_id '{v}' contains invalid characters. "
                "Must be lowercase alphanumeric and underscores only (e.g. 'acme' or 'acme_corp'). "
                "Hyphens and spaces are not allowed because client_id is used in DB schema and queue names."
            )
        return v

    @field_validator("target_timezone", mode="after")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate against pytz timezone database."""
        try:
            import pytz

            pytz.timezone(v)
        except Exception:
            raise ValueError(
                f"Invalid timezone '{v}'. Must be a valid pytz timezone string, "
                "e.g. 'America/Chicago', 'America/New_York', 'Europe/London'. "
                "See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
            )
        return v

    @field_validator("personas", mode="after")
    @classmethod
    def validate_all_personas_present(cls, v: dict[str, PersonaConfig]) -> dict[str, PersonaConfig]:
        """All 6 persona types must be defined. Missing personas block the whole pipeline."""
        missing = REQUIRED_PERSONAS - set(v.keys())
        if missing:
            raise ValueError(
                f"Personas config is missing required persona types: {sorted(missing)}. "
                f"All 6 types are required: {sorted(REQUIRED_PERSONAS)}. "
                "Add the missing persona blocks to the config JSON."
            )
        return v


# ── Public loader function ─────────────────────────────────────────────────────


def load_client_config(
    client_id: str,
    configs_dir: Optional[Path] = None,
) -> ClientConfig:
    """
    Load and validate the client configuration JSON for ``client_id``.

    Args:
        client_id:   The client slug. Config file must be at configs/{client_id}.json.
        configs_dir: Override the default configs directory (used in tests).

    Returns:
        Validated ClientConfig instance.

    Raises:
        ConfigNotFoundError:   Config file does not exist.
        ConfigValidationError: JSON is malformed, a required field is missing,
                               a field value is invalid, or an SMTP env var is not set.
    """
    if configs_dir is None:
        configs_dir = CONFIGS_DIR

    config_path = configs_dir / f"{client_id}.json"

    if not config_path.exists():
        raise ConfigNotFoundError(
            f"Config file not found for client '{client_id}': {config_path}. "
            f"Create configs/{client_id}.json using configs/client_example.json as a template."
        )

    try:
        raw: Any = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(
            f"Config file for client '{client_id}' contains invalid JSON at "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(raw, dict):
        raise ConfigValidationError(
            f"Config file for client '{client_id}' must be a JSON object ({{...}}), "
            f"got {type(raw).__name__}."
        )

    try:
        config = ClientConfig.model_validate(raw)
    except ConfigValidationError:
        # Re-raise our own exceptions (e.g. from SMTP password resolver)
        raise
    except Exception as exc:
        raise ConfigValidationError(
            f"Config validation failed for client '{client_id}': {exc}"
        ) from exc

    # Verify the client_id in the file matches the requested client_id
    if config.client_id != client_id:
        raise ConfigValidationError(
            f"client_id mismatch: config file declares client_id='{config.client_id}' "
            f"but was loaded as client_id='{client_id}' (from filename '{client_id}.json'). "
            "Update the client_id field in the JSON to match the filename."
        )

    return config
