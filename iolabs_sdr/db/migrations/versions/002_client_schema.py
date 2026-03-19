"""Create per-client schema and all per-client tables.

Revision ID: 002
Revises: 001
Create Date: 2026-03-19

PARAMETRIC — must be run with -x client_schema=client_{id}:
    alembic upgrade 002 -x client_schema=client_acme

Also called by scripts/provision_client.py (Step 5) which passes the
client_schema automatically.

Tables created (all within the specified client schema):
  leads
  contacts
  emails_sent
  email_replies
  linkedin_messages
  dnc_list
  sequence_schedule

Also creates:
  - update_updated_at_column() trigger function (if not exists)
  - updated_at trigger on leads and contacts tables
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_client_schema() -> str:
    """
    Read client_schema from Alembic -x argument.
    Falls back to search_path if already set (used by provision_client.py).
    """
    x = context.get_x_argument(as_dictionary=True)
    schema = x.get("client_schema", "")
    if not schema:
        raise RuntimeError(
            "client_schema is required. Run: alembic upgrade 002 -x client_schema=client_{id}"
        )
    return schema


# ── Migration ──────────────────────────────────────────────────────────────────


def upgrade() -> None:
    schema = _get_client_schema()

    # ── Create client schema ────────────────────────────────────────────────
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # ── Enable pgvector (idempotent) ────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── leads ───────────────────────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("place_id", sa.String(255), unique=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("phone", sa.String(64)),
        sa.Column("website", sa.String(512)),
        sa.Column("linkedin_url", sa.String(512)),
        sa.Column("google_category", sa.String(255)),
        sa.Column("rating", sa.Numeric(3, 1)),
        sa.Column("review_count", sa.Integer),
        sa.Column("tier", sa.String(32)),
        sa.Column("classification_score", sa.Numeric(6, 2)),
        sa.Column("signals", JSONB),
        sa.Column("screenshot_paths", JSONB),
        sa.Column("status", sa.String(32), nullable=False, server_default="'raw'"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=schema,
    )

    # ── contacts ─────────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "lead_id",
            sa.BigInteger,
            sa.ForeignKey(f"{schema}.leads.id"),
        ),
        sa.Column(
            "cid",
            UUID(as_uuid=True),
            unique=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("first_name", sa.String(128)),
        sa.Column("last_name", sa.String(128)),
        sa.Column("title", sa.String(255)),
        sa.Column("persona", sa.String(64)),
        sa.Column("email", sa.String(512)),
        sa.Column(
            "email_status", sa.String(32), nullable=False, server_default="'unknown'"
        ),
        sa.Column("linkedin_url", sa.String(512)),
        sa.Column("linkedin_status", sa.String(32)),
        sa.Column("sequence_stage", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "sequence_paused", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column(
            "status", sa.String(64), nullable=False, server_default="'pending'"
        ),
        sa.Column("dnc", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=schema,
    )

    # ── emails_sent ───────────────────────────────────────────────────────────
    op.create_table(
        "emails_sent",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "contact_id",
            sa.BigInteger,
            sa.ForeignKey(f"{schema}.contacts.id"),
        ),
        sa.Column("email_num", sa.Integer, nullable=False),
        sa.Column(
            "sent_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("subject", sa.String(512)),
        sa.Column("message_id", sa.String(512)),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("clicked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("open_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("click_count", sa.Integer, nullable=False, server_default="0"),
        schema=schema,
    )

    # ── email_replies ─────────────────────────────────────────────────────────
    op.create_table(
        "email_replies",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "contact_id",
            sa.BigInteger,
            sa.ForeignKey(f"{schema}.contacts.id"),
        ),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("raw_body", sa.Text),
        sa.Column("reply_type", sa.String(32)),
        sa.Column("reply_confidence", sa.Numeric(4, 3)),
        sa.Column("handled_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("handler_action", sa.String(128)),
        schema=schema,
    )

    # ── linkedin_messages ─────────────────────────────────────────────────────
    op.create_table(
        "linkedin_messages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "contact_id",
            sa.BigInteger,
            sa.ForeignKey(f"{schema}.contacts.id"),
        ),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column(
            "sent_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("body", sa.Text),
        sa.Column("reply_type", sa.String(32)),
        sa.Column("handled_at", sa.TIMESTAMP(timezone=True)),
        schema=schema,
    )

    # ── dnc_list ──────────────────────────────────────────────────────────────
    op.create_table(
        "dnc_list",
        sa.Column("email", sa.String(512), primary_key=True),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("reason", sa.String(128)),
        schema=schema,
    )

    # ── sequence_schedule ─────────────────────────────────────────────────────
    op.create_table(
        "sequence_schedule",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "contact_id",
            sa.BigInteger,
            sa.ForeignKey(f"{schema}.contacts.id"),
        ),
        sa.Column("task_name", sa.String(128)),
        sa.Column("scheduled_for", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="'pending'"
        ),
        sa.Column("celery_task_id", sa.String(255)),
        schema=schema,
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.create_index("ix_leads_status", "leads", ["status"], schema=schema)
    op.create_index("ix_leads_tier", "leads", ["tier"], schema=schema)
    op.create_index("ix_contacts_email", "contacts", ["email"], schema=schema)
    op.create_index("ix_contacts_status", "contacts", ["status"], schema=schema)
    op.create_index("ix_contacts_dnc", "contacts", ["dnc"], schema=schema)
    op.create_index(
        "ix_sequence_schedule_contact_status",
        "sequence_schedule",
        ["contact_id", "status"],
        schema=schema,
    )

    # ── updated_at trigger (server-side auto-update) ───────────────────────────
    # Ensures updated_at is always accurate even for raw SQL updates.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_leads_updated_at
            BEFORE UPDATE ON {schema}.leads
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_contacts_updated_at
            BEFORE UPDATE ON {schema}.contacts
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    schema = _get_client_schema()

    op.drop_table("sequence_schedule", schema=schema)
    op.drop_table("dnc_list", schema=schema)
    op.drop_table("linkedin_messages", schema=schema)
    op.drop_table("email_replies", schema=schema)
    op.drop_table("emails_sent", schema=schema)
    op.drop_table("contacts", schema=schema)
    op.drop_table("leads", schema=schema)
    op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
