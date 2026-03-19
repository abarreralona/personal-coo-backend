"""
Alembic migration environment — IOlabs AI SDR Platform (Step 3).

Supports two migration targets selected via -x argument:

    # Platform schema (default — no -x needed):
    alembic upgrade head

    # Per-client schema:
    alembic upgrade head -x client_schema=client_acme

Uses async SQLAlchemy engine (asyncpg driver).
URL is taken from DATABASE_URL env var or alembic.ini sqlalchemy.url.
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Path setup ──────────────────────────────────────────────────────────────
# Ensure the project root (iolabs_sdr/) is on sys.path so db.models is importable.
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from db.models import client_metadata, platform_metadata  # noqa: E402

# ── Alembic config ──────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── x-argument: client_schema ───────────────────────────────────────────────
# If -x client_schema=client_acme is passed, migrate that per-client schema.
# Otherwise, migrate the platform schema.
_x_args = context.get_x_argument(as_dictionary=True)
_client_schema: str | None = _x_args.get("client_schema")

target_metadata = client_metadata if _client_schema else platform_metadata


# ── DB URL ──────────────────────────────────────────────────────────────────

def _get_url() -> str:
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")
    # Ensure the async driver scheme is used
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Export it before running alembic, "
            "e.g.: export DATABASE_URL=postgresql+asyncpg://user:pass@host/db"
        )
    return url


# ── Offline mode ─────────────────────────────────────────────────────────────

# When provisioning a per-client schema, store alembic_version in that client's
# own schema — each tenant tracks its own migration history independently.
# For the platform schema, store alembic_version in the platform schema.
_version_table_schema: str = _client_schema if _client_schema else "platform"


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_version",
        version_table_schema=_version_table_schema,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ───────────────────────────────────────────────────────────────

def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table="alembic_version",
        version_table_schema=_version_table_schema,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _get_url()

    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # new connection per migration run
    )

    async with connectable.connect() as connection:
        if _client_schema:
            # Set search_path so per-client DDL lands in the correct schema
            await connection.execute(text(f"SET search_path TO {_client_schema}, public"))
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


# ── Entry point ───────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(_run_migrations_online())
