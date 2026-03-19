"""
IOlabs AI SDR Platform — Per-Client DB Session Router (Step 3)

Two public context managers:

    get_client_session(client_id)  → AsyncSession scoped to client_{id} schema
    get_platform_session()         → AsyncSession scoped to platform schema

Schema routing uses PostgreSQL's search_path:
    SET search_path TO client_{client_id}, public

This is safe with SQLAlchemy connection pooling in the Celery worker context
because each worker task:
    1. Acquires a session
    2. Sets search_path for that session
    3. Performs all DB work
    4. Commits and closes — connection returned to pool

The pool's `pool_pre_ping=True` detects and replaces stale connections.
The next task that checks out the connection sets its own search_path immediately.

Security: client_id is validated against [a-z0-9_]+ before use in SET statement
to prevent SQL injection (defence-in-depth on top of config loader validation).
"""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Engine ─────────────────────────────────────────────────────────────────────

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://iolabs:changeme@localhost:5432/iolabs_sdr",
)

engine = create_async_engine(
    _DATABASE_URL,
    echo=os.environ.get("DB_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # prevent lazy-load errors after commit in async context
)

# ── Validation ─────────────────────────────────────────────────────────────────

_SAFE_SCHEMA_NAME_RE = re.compile(r"^[a-z0-9_]+$")


def _validate_client_id(client_id: str) -> None:
    """
    Guard against SQL injection in schema names.
    client_id is used directly in SET search_path — must contain only safe chars.
    Config loader enforces this at load time; we re-validate here as defence-in-depth.
    """
    if not _SAFE_SCHEMA_NAME_RE.match(client_id):
        raise ValueError(
            f"client_id '{client_id}' contains characters unsafe for use in a PostgreSQL "
            "schema name. Must be lowercase alphanumeric + underscores only."
        )


# ── Session context managers ────────────────────────────────────────────────────


@asynccontextmanager
async def get_client_session(client_id: str) -> AsyncIterator[AsyncSession]:
    """
    Yield an AsyncSession with search_path scoped to client_{client_id}.

    All queries against ClientBase models (Lead, Contact, EmailSent, etc.)
    within this context resolve to the correct per-client PostgreSQL schema.

    Usage:
        async with get_client_session("acme") as session:
            result = await session.execute(select(Lead).where(Lead.status == "raw"))
            leads = result.scalars().all()
            await session.commit()

    Args:
        client_id: Client slug (e.g. "acme"). Must be lowercase alphanumeric + underscores.

    Raises:
        ValueError: If client_id contains unsafe characters.
    """
    _validate_client_id(client_id)
    schema_name = f"client_{client_id}"

    async with _session_factory() as session:
        await session.execute(text(f"SET search_path TO {schema_name}, public"))
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_platform_session() -> AsyncIterator[AsyncSession]:
    """
    Yield an AsyncSession with search_path scoped to the platform schema.

    Usage:
        async with get_platform_session() as session:
            result = await session.execute(select(Tenant).where(Tenant.active.is_(True)))
            tenants = result.scalars().all()
            await session.commit()
    """
    async with _session_factory() as session:
        await session.execute(text("SET search_path TO platform, public"))
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
