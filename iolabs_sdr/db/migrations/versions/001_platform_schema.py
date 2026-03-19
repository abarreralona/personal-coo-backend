"""Create platform schema and all platform tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-19

Run with: alembic upgrade head
(no -x argument needed for platform schema)

Tables created:
  platform.tenants
  platform.audit_log
  platform.campaign_results
  platform.dnc_global
  platform.seed_files
  platform.mirror_fish_runs
  platform.campaign_plans
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create platform schema ──────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS platform")

    # ── platform.tenants ───────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("config_path", sa.String(512)),
        sa.Column("db_schema", sa.String(64)),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("client_id", name="uq_tenants_client_id"),
        schema="platform",
    )

    # ── platform.audit_log ──────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("stage", sa.String(64)),
        sa.Column("action", sa.String(128)),
        sa.Column("entity_id", sa.String(128)),
        sa.Column("status", sa.String(32)),
        sa.Column("message", sa.Text),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )

    # ── platform.campaign_results ───────────────────────────────────────────
    op.create_table(
        "campaign_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("campaign_id", sa.String(128)),
        sa.Column("copy_set_id", sa.String(128)),
        sa.Column("persona", sa.String(64)),
        sa.Column("city", sa.String(128)),
        sa.Column("industry", sa.String(128)),
        sa.Column("sent_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("open_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("click_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reply_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("positive_reply_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("not_interested_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unsubscribe_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("wrong_email_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ooo_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("complex_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("open_rate", sa.Numeric(5, 4)),
        sa.Column("reply_rate", sa.Numeric(5, 4)),
        sa.Column("positive_reply_rate", sa.Numeric(5, 4)),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )

    # ── platform.dnc_global ─────────────────────────────────────────────────
    op.create_table(
        "dnc_global",
        sa.Column("email", sa.String(512), primary_key=True),
        sa.Column("domain", sa.String(255)),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("reason", sa.String(128)),
        schema="platform",
    )

    # ── platform.seed_files ─────────────────────────────────────────────────
    op.create_table(
        "seed_files",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("industry_key", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("approved_by", sa.String(128)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "industry_key", "version", name="uq_seed_files_industry_version"
        ),
        schema="platform",
    )

    # ── platform.mirror_fish_runs ───────────────────────────────────────────
    op.create_table(
        "mirror_fish_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("copy_set_id", sa.String(128)),
        sa.Column("industry_key", sa.String(128)),
        sa.Column("persona_results", JSONB),
        sa.Column("overall_risk_score", sa.Numeric(5, 2)),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="'completed'"
        ),
        sa.Column("approved_by", sa.String(128)),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )

    # ── platform.campaign_plans ─────────────────────────────────────────────
    op.create_table(
        "campaign_plans",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(64)),
        sa.Column("directive", sa.Text),
        sa.Column("ranked_cities", JSONB),
        sa.Column("copy_set_id", sa.String(128)),
        sa.Column(
            "mirror_fish_run_id",
            sa.BigInteger,
            sa.ForeignKey("platform.mirror_fish_runs.id"),
        ),
        sa.Column("risk_flags", JSONB),
        sa.Column("estimated_timeline", JSONB),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="'pending_approval'",
        ),
        sa.Column("approved_by", sa.String(128)),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )

    # ── Indexes ─────────────────────────────────────────────────────────────
    op.create_index(
        "ix_audit_log_client_id", "audit_log", ["client_id"], schema="platform"
    )
    op.create_index(
        "ix_audit_log_timestamp", "audit_log", ["timestamp"], schema="platform"
    )
    op.create_index(
        "ix_campaign_results_client_id",
        "campaign_results",
        ["client_id"],
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("campaign_plans", schema="platform")
    op.drop_table("mirror_fish_runs", schema="platform")
    op.drop_table("seed_files", schema="platform")
    op.drop_table("dnc_global", schema="platform")
    op.drop_table("campaign_results", schema="platform")
    op.drop_table("audit_log", schema="platform")
    op.drop_table("tenants", schema="platform")
    op.execute("DROP SCHEMA IF EXISTS platform CASCADE")
