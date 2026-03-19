"""
IOlabs AI SDR Platform — Tenant Schema Helper (Step 3)

Thin helpers for deriving per-client schema names and performing
id-format validation. All session-level routing lives in db/session.py.
"""

from __future__ import annotations

import re

_SAFE_CLIENT_ID_RE = re.compile(r"^[a-z0-9_]+$")


def get_tenant_schema(client_id: str) -> str:
    """
    Return the PostgreSQL schema name for a given client.

    Args:
        client_id: Client slug — must be lowercase alphanumeric + underscores.

    Returns:
        Schema name string, e.g. "client_acme".

    Raises:
        ValueError: If client_id contains unsafe characters.
    """
    if not _SAFE_CLIENT_ID_RE.match(client_id):
        raise ValueError(
            f"client_id '{client_id}' must be lowercase alphanumeric + underscores only."
        )
    return f"client_{client_id}"


def validate_client_id(client_id: str) -> None:
    """
    Raise ValueError if client_id is not a safe schema-name slug.
    Thin convenience wrapper around get_tenant_schema validation.
    """
    get_tenant_schema(client_id)
