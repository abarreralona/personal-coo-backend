"""
IOlabs AI SDR Platform — SQLAlchemy 2.0 ORM Models (Step 3)

Two schema families:

  PlatformBase (schema='platform')
    Tenant, AuditLog, CampaignResult, DNCGlobal,
    SeedFile, MirrorFishRun, CampaignPlan

  ClientBase (no schema — routing via SET search_path TO client_{id})
    Lead, Contact, EmailSent, EmailReply,
    LinkedInMessage, DNCList, SequenceSchedule

DDL spec: Section 7.
Schema routing: db/session.py → get_client_session() / get_platform_session()
Provisioning: scripts/provision_client.py (Step 5)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ── Metadata ──────────────────────────────────────────────────────────────────

# Platform schema — shared across all tenants.
platform_metadata = MetaData(schema="platform")

# Per-client schema — NO schema prefix.
# All queries against ClientBase models must be wrapped in a session that has
# executed: SET search_path TO client_{client_id}, public
# See: db/session.py → get_client_session()
client_metadata = MetaData()


# ── Base classes ──────────────────────────────────────────────────────────────


class PlatformBase(DeclarativeBase):
    """Base for all platform.* tables (shared, not per-client)."""

    metadata = platform_metadata


class ClientBase(DeclarativeBase):
    """
    Base for all client_{id}.* tables.
    No schema — routing via search_path at session level.
    """

    metadata = client_metadata


# ═════════════════════════════════════════════════════════════════════════════
# PLATFORM TABLES  (platform.*)
# ═════════════════════════════════════════════════════════════════════════════


class Tenant(PlatformBase):
    """
    Registry of all active client tenants.
    Populated by scripts/provision_client.py (Step 5).
    """

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    config_path: Mapped[Optional[str]] = mapped_column(String(512))
    db_schema: Mapped[Optional[str]] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class AuditLog(PlatformBase):
    """
    Structured audit log for every pipeline event.
    Written at each stage transition, error, and business rule enforcement.
    Acceptance criterion (Section 12): every pipeline event must appear here
    with client_id, stage, entity_id, status, message.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64))
    stage: Mapped[Optional[str]] = mapped_column(String(64))
    action: Mapped[Optional[str]] = mapped_column(String(128))
    entity_id: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[Optional[str]] = mapped_column(String(32))
    message: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class CampaignResult(PlatformBase):
    """
    Aggregated campaign performance metrics per client / campaign / persona / city.
    Read by Open Claw (anomaly detection) and Mirror Fish (feedback analyzer).
    """

    __tablename__ = "campaign_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64))
    campaign_id: Mapped[Optional[str]] = mapped_column(String(128))
    copy_set_id: Mapped[Optional[str]] = mapped_column(String(128))
    persona: Mapped[Optional[str]] = mapped_column(String(64))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    industry: Mapped[Optional[str]] = mapped_column(String(128))
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    positive_reply_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    not_interested_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    unsubscribe_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    wrong_email_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ooo_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    complex_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    open_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    reply_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    positive_reply_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class DNCGlobal(PlatformBase):
    """
    Platform-wide Do-Not-Contact list. Checked at SMTP send time (Business Rule 1)
    in addition to the per-client dnc_list.
    email is the primary key — guarantees uniqueness without a separate id.
    """

    __tablename__ = "dnc_global"

    email: Mapped[str] = mapped_column(String(512), primary_key=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255))
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    reason: Mapped[Optional[str]] = mapped_column(String(128))


class SeedFile(PlatformBase):
    """
    Versioned Mirror Fish industry seed files.
    Each (industry_key, version) pair is unique.
    New versions are created when the feedback_analyzer proposes changes
    and an operator approves them.

    TODO: OPEN ITEM 2 — First seed file for packaging_distribution_midmarket
    must be written by IOlabs operator before Mirror Fish Phase 3 development.
    """

    __tablename__ = "seed_files"
    __table_args__ = (
        UniqueConstraint("industry_key", "version", name="uq_seed_files_industry_version"),
        {"schema": "platform"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    industry_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class MirrorFishRun(PlatformBase):
    """
    Record of each Mirror Fish simulation run.
    Linked to CampaignPlan via mirror_fish_run_id.
    """

    __tablename__ = "mirror_fish_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64))
    copy_set_id: Mapped[Optional[str]] = mapped_column(String(128))
    industry_key: Mapped[Optional[str]] = mapped_column(String(128))
    persona_results: Mapped[Optional[dict]] = mapped_column(JSONB)
    overall_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="'completed'"
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(128))
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class CampaignPlan(PlatformBase):
    """
    Open Claw campaign plan. Requires human approval before EXECUTING state.
    State machine: RECON → PLANNING → PENDING_APPROVAL → EXECUTING → MONITORING → COMPLETED | PAUSED
    Human approval is mandatory — the agent checks approved_at before enqueuing any pipeline task.
    """

    __tablename__ = "campaign_plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64))
    directive: Mapped[Optional[str]] = mapped_column(Text)
    ranked_cities: Mapped[Optional[dict]] = mapped_column(JSONB)
    copy_set_id: Mapped[Optional[str]] = mapped_column(String(128))
    mirror_fish_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("platform.mirror_fish_runs.id")
    )
    risk_flags: Mapped[Optional[dict]] = mapped_column(JSONB)
    estimated_timeline: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="'pending_approval'"
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(128))
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# ═════════════════════════════════════════════════════════════════════════════
# PER-CLIENT TABLES  (client_{id}.*)
# No schema prefix — search_path routing via get_client_session()
# ═════════════════════════════════════════════════════════════════════════════


class Lead(ClientBase):
    """
    A discovered company from Stage 1 (Lead Discovery).
    Progresses through: raw → classified → disqualified | enriched
    screenshot_paths: JSONB {"homepage": path, "logos_section": path, "products": path}
    signals: JSONB — full audit trail of signal evaluations from classifier
    """

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    place_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    website: Mapped[Optional[str]] = mapped_column(String(512))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(512))
    google_category: Mapped[Optional[str]] = mapped_column(String(255))
    rating: Mapped[Optional[float]] = mapped_column(Numeric(3, 1))
    review_count: Mapped[Optional[int]] = mapped_column(Integer)
    tier: Mapped[Optional[str]] = mapped_column(String(32))
    classification_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    signals: Mapped[Optional[dict]] = mapped_column(JSONB)
    screenshot_paths: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="'raw'")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class Contact(ClientBase):
    """
    A discovered person at a Lead company.
    cid (UUID) is the public tracking identifier used in pixel/click URLs.
    Progresses through sequence stages; sequence_paused blocks all email sends.

    Business Rule 1: DNC check uses this record's email at SMTP send time.
    Business Rule 4: When dnc=True, all pending SequenceSchedule tasks must be
                     revoked immediately via Celery revoke().
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("leads.id"))
    cid: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        unique=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    last_name: Mapped[Optional[str]] = mapped_column(String(128))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    persona: Mapped[Optional[str]] = mapped_column(String(64))
    email: Mapped[Optional[str]] = mapped_column(String(512))
    email_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="'unknown'"
    )
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(512))
    linkedin_status: Mapped[Optional[str]] = mapped_column(String(32))
    sequence_stage: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sequence_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(String(64), nullable=False, server_default="'pending'")
    dnc: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class EmailSent(ClientBase):
    """
    Record of each email sent in the sequence.
    opened_at and clicked_at are set by the webhook endpoints (Step 14).
    Acceptance criterion: opened_at written within 5 seconds of pixel GET.
    """

    __tablename__ = "emails_sent"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("contacts.id"))
    email_num: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    subject: Mapped[Optional[str]] = mapped_column(String(512))
    message_id: Mapped[Optional[str]] = mapped_column(String(512))
    opened_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    clicked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class EmailReply(ClientBase):
    """
    Inbound email reply record.
    reply_type: one of the 7 reply states (Section 6).
    reply_confidence: 0.000–1.000, set by LLM classifier.
    """

    __tablename__ = "email_replies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("contacts.id"))
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    raw_body: Mapped[Optional[str]] = mapped_column(Text)
    reply_type: Mapped[Optional[str]] = mapped_column(String(32))
    reply_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    handled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    handler_action: Mapped[Optional[str]] = mapped_column(String(128))


class LinkedInMessage(ClientBase):
    """
    LinkedIn inbound/outbound messages.
    direction: 'in' or 'out' (VARCHAR(8) per spec).
    Reuses same 7-state reply classifier as email replies.
    """

    __tablename__ = "linkedin_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("contacts.id"))
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    body: Mapped[Optional[str]] = mapped_column(Text)
    reply_type: Mapped[Optional[str]] = mapped_column(String(32))
    handled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class DNCList(ClientBase):
    """
    Per-client Do-Not-Contact list.
    Business Rule 1: checked at SMTP send time in email/sender.py.
    Business Rule 4: UNSUBSCRIBE reply → INSERT here + cancel all pending tasks.
    email is PK — guarantees uniqueness without a separate id column.
    """

    __tablename__ = "dnc_list"

    email: Mapped[str] = mapped_column(String(512), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    reason: Mapped[Optional[str]] = mapped_column(String(128))


class SequenceSchedule(ClientBase):
    """
    Scheduled email sequence tasks for each contact.
    celery_task_id is used to revoke tasks on DNC/UNSUBSCRIBE/NOT_INTERESTED
    (Business Rule 4: cancel ALL pending tasks immediately via celery.control.revoke()).
    status: pending | sent | cancelled | skipped
    """

    __tablename__ = "sequence_schedule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("contacts.id"))
    task_name: Mapped[Optional[str]] = mapped_column(String(128))
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="'pending'")
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255))
