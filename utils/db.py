# utils/db.py
import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

# Use Render persistent disk if available (mount /var/data on Render)
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/coo_backend.db"))

# -----------------------------
# Low-level helpers / bootstrap
# -----------------------------

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Creates tables if they don't exist and adds missing columns if you had
    an older version. Safe to call on every startup.
    """
    # Tokens: store entire token payload + expiry + scopes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            token_payload TEXT NOT NULL,
            token_expiry TEXT,
            scopes TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, provider)
        )
    """)

    # Backward-compatible column additions (no-op if they already exist)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(tokens)")]
    if "token_expiry" not in cols:
        conn.execute("ALTER TABLE tokens ADD COLUMN token_expiry TEXT")
    if "scopes" not in cols:
        conn.execute("ALTER TABLE tokens ADD COLUMN scopes TEXT")
    if "updated_at" not in cols:
        conn.execute("ALTER TABLE tokens ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")

    # Simple memory store used by /v1/memory/*
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mem_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            text TEXT NOT NULL,
            tags TEXT,
            strength REAL DEFAULT 0.7,
            created_at TEXT
        )
    """)

def init_db() -> None:
    with _get_conn() as conn:
        _ensure_schema(conn)
        conn.commit()

# -----------------------------
# OAuth token storage
# -----------------------------

def upsert_token(
    user_id: str,
    provider: str,
    token_payload: Dict[str, Any],
    token_expiry: Optional[str],
    scopes: str,
) -> None:
    """
    Save/replace the token for (user_id, provider).
    token_payload is stored as JSON (includes access_token, refresh_token, etc.)
    """
    payload_json = json.dumps(token_payload)
    now = datetime.utcnow().isoformat()

    with _get_conn() as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO tokens (user_id, provider, token_payload, token_expiry, scopes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
                token_payload = excluded.token_payload,
                token_expiry  = excluded.token_expiry,
                scopes        = excluded.scopes,
                updated_at    = excluded.updated_at
            """,
            (user_id, provider, payload_json, token_expiry, scopes, now),
        )
        conn.commit()

def get_token(user_id: str, provider: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tokens WHERE user_id=? AND provider=?",
            (user_id, provider),
        ).fetchone()

    if not row:
        return None

    return {
        "user_id": row["user_id"],
        "provider": row["provider"],
        "token_payload": json.loads(row["token_payload"]),
        "token_expiry": row["token_expiry"],
        "scopes": row["scopes"],
        "updated_at": row["updated_at"],
    }

# -----------------------------
# Memory helpers
# -----------------------------

def write_memory(
    user_id: str,
    kind: str,
    text: str,
    tags: Optional[List[str]] = None,
    strength: float = 0.7,
) -> None:
    tag_str = ",".join(tags or [])
    now = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO mem_chunks(user_id, kind, text, tags, strength, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, kind, text, tag_str, strength, now),
        )
        conn.commit()

def search_memory(
    user_id: str,
    query: str,
    kinds: Optional[List[str]] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    base = "SELECT * FROM mem_chunks WHERE user_id=?"
    params: List[Any] = [user_id]

    if kinds:
        base += " AND kind IN (%s)" % ",".join("?" * len(kinds))
        params.extend(kinds)

    if query:
        base += " AND text LIKE ?"
        params.append(f"%{query}%")

    base += " ORDER BY created_at DESC LIMIT ?"
    params.append(top_k)

    with _get_conn() as conn:
        rows = [dict(r) for r in conn.execute(base, params).fetchall()]
    return rows

def recent_memory(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM mem_chunks WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]

def delete_memory(memory_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM mem_chunks WHERE id=?", (memory_id,))
        conn.commit()

