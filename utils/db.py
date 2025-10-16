from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

# Use a persistent disk path on Render if provided
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/coo_backend.db")).resolve()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create required tables if they don't exist."""
    with _connect() as conn:
        c = conn.cursor()

        # OAuth tokens
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                provider TEXT PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT,
                token_expiry TEXT,
                scopes TEXT,
                updated_at TEXT
            )
            """
        )

        # (Optional) simple memory table – keep if you already use it
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                source TEXT,
                score REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
            """
        )
        conn.commit()


def upsert_token(
    provider: str,
    access_token: str,
    refresh_token: str,
    token_expiry: str,
    scopes: str = "",
) -> None:
    """Insert or update OAuth tokens for a provider. Scopes are required by our app."""
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO oauth_tokens(provider, access_token, refresh_token, token_expiry, scopes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                token_expiry=excluded.token_expiry,
                scopes=excluded.scopes,
                updated_at=excluded.updated_at
            """,
            (provider, access_token, refresh_token, token_expiry, scopes, now),
        )
        conn.commit()


def get_token(provider: str) -> Optional[Dict[str, Any]]:
    """Fetch the token row for a provider as a dict."""
    with _connect() as conn:
        c = conn.cursor()
        row = c.execute(
            "SELECT provider, access_token, refresh_token, token_expiry, scopes, updated_at FROM oauth_tokens WHERE provider=?",
            (provider,),
        ).fetchone()
    return dict(row) if row else None

