import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Iterable
from datetime import datetime

# Where the persistent DB lives on Render (or override via env)
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/coo_backend.db"))

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- helpers ----------

def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row["name"] for row in cur.fetchall()}

def _ensure_columns(conn: sqlite3.Connection, table: str, columns_sql: Dict[str, str]) -> None:
    """
    Add columns to `table` if they're missing.
    columns_sql: {"col_name": "TEXT", ...}
    """
    existing = _table_columns(conn, table)
    for col, sql_type in columns_sql.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {sql_type}")

def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")

# ---------- schema / init ----------

def init_db() -> None:
    """
    Idempotent initialization + migration.
    Ensures:
      - oauth_tokens (provider PK, access/refresh/expiry/scopes, created_at, updated_at)
      - memories (if you use it elsewhere)
    """
    conn = _connect()
    try:
        # Create oauth_tokens if missing (with the full modern set of columns)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            provider TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            token_expiry TEXT,
            scopes TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """)

        # Migrate an older table forward by adding any missing columns
        _ensure_columns(
            conn,
            "oauth_tokens",
            {
                "access_token": "TEXT",
                "refresh_token": "TEXT",
                "token_expiry": "TEXT",
                "scopes": "TEXT",
                "created_at": "TEXT",
                "updated_at": "TEXT",
            },
        )

        # (Optional) minimal memories table, keep if you’re using it
        conn.execute("""
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
        """)
        conn.commit()
    finally:
        conn.close()

# ---------- tokens API ----------

def get_token(provider: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT provider, access_token, refresh_token, token_expiry, scopes, created_at, updated_at "
            "FROM oauth_tokens WHERE provider = ?",
            (provider,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def upsert_token(
    provider: str,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    token_expiry: Optional[str] = None,
    scopes: Optional[str] = None,
) -> None:
    """
    Robust UPSERT that adapts to the actual columns present in oauth_tokens.
    This makes it safe on old DBs and after migrations.
    """
    conn = _connect()
    try:
        cols = _table_columns(conn, "oauth_tokens")

        # Determine which columns we can write
        payload: Dict[str, Any] = {"provider": provider}
        if "access_token" in cols and access_token is not None:
            payload["access_token"] = access_token
        if "refresh_token" in cols and refresh_token is not None:
            payload["refresh_token"] = refresh_token
        if "token_expiry" in cols and token_expiry is not None:
            payload["token_expiry"] = token_expiry
        if "scopes" in cols and scopes is not None:
            payload["scopes"] = scopes

        now = _now_iso()
        if "created_at" in cols:
            # created_at only set on first insert — we’ll use COALESCE trick below
            payload.setdefault("created_at", now)
        if "updated_at" in cols:
            payload["updated_at"] = now

        # Build dynamic INSERT ... ON CONFLICT(provider) DO UPDATE ...
        column_names: Iterable[str] = payload.keys()
        insert_cols = ", ".join(column_names)
        insert_qs = ", ".join("?" for _ in column_names)

        # Update assignments (skip provider, and usually skip created_at)
        update_parts = []
        for c in payload.keys():
            if c == "provider":
                continue
            if c == "created_at":
                # preserve original created_at if row already exists
                update_parts.append(f"{c}=COALESCE({c}, excluded.{c})")
            else:
                update_parts.append(f"{c}=excluded.{c}")
        update_sql = ", ".join(update_parts) if update_parts else ""

        sql = (
            f"INSERT INTO oauth_tokens ({insert_cols}) VALUES ({insert_qs}) "
            f"ON CONFLICT(provider) DO UPDATE SET {update_sql}"
        )

        conn.execute(sql, tuple(payload.values()))
        conn.commit()
    finally:
        conn.close()


