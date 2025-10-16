import os
import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Where the DB lives (use Render disk when present)
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/coo_backend.db"))

def _ensure_parent():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _connect():
    _ensure_parent()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Creates all tables we need. Safe to call on every startup.
    """
    conn = _connect()
    c = conn.cursor()

    # OAuth tokens (supports multiple users and providers)
    c.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        user_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        access_token TEXT,
        refresh_token TEXT,
        token_json TEXT,       -- full payload for convenience
        token_expiry TEXT,     -- ISO datetime or NULL
        scopes TEXT,           -- space-separated scopes
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (user_id, provider)
    )
    """)

    # Agent memory
    c.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,     -- e.g. the owner email or 'default'
        agent_id TEXT NOT NULL,    -- e.g. 'personal-coo'
        scope TEXT NOT NULL,       -- 'short' | 'long' | 'team'
        content TEXT NOT NULL,
        tags TEXT,                 -- comma-separated
        source TEXT,               -- 'manual' | 'gmail' | 'odoo' | 'chat'
        score REAL DEFAULT 0,
        created_at TEXT NOT NULL,
        expires_at TEXT            -- NULL for long-term
    )
    """)

    conn.commit()
    conn.close()

# ----------------------------
# OAuth token helpers
# ----------------------------

def upsert_token(
    user_id: str,
    provider: str,
    token_payload: Dict[str, Any],
    token_expiry: Optional[str],
    scopes: Optional[str]
) -> None:
    """
    Stores or updates a token. 'token_payload' is the full dict you get from Google Flow.
    """
    now = datetime.utcnow().isoformat()
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token")

    conn = _connect()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tokens (user_id, provider, access_token, refresh_token, token_json, token_expiry, scopes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, provider) DO UPDATE SET
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            token_json=excluded.token_json,
            token_expiry=excluded.token_expiry,
            scopes=excluded.scopes,
            updated_at=excluded.updated_at
    """, (
        user_id,
        provider,
        access_token,
        refresh_token,
        json.dumps(token_payload),
        token_expiry,
        scopes or "",
        now,
        now,
    ))
    conn.commit()
    conn.close()

def get_token(user_id: str, provider: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    c = conn.cursor()
    row = c.execute(
        "SELECT * FROM tokens WHERE user_id=? AND provider=?",
        (user_id, provider)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("token_json"):
        d["token_json"] = json.loads(d["token_json"])
    return d

# ----------------------------
# Memory helpers
# ----------------------------

def write_memory(
    user_id: str,
    kind_or_scope: str,   # keep compatibility with earlier code
    text: str,
    tags: Optional[List[str]] = None,
    strength: float = 0.7,
    agent_id: str = "personal-coo",
    source: str = "manual",
    ttl_days: Optional[int] = None
) -> None:
    """
    Writes a memory row. If ttl_days is provided we set expires_at accordingly.
    """
    now = datetime.utcnow()
    expires_at = (now + timedelta(days=ttl_days)).isoformat() if ttl_days else None

    conn = _connect()
    c = conn.cursor()
    c.execute("""
        INSERT INTO memories (user_id, agent_id, scope, content, tags, source, score, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        agent_id,
        kind_or_scope,
        text,
        ",".join(tags or []),
        source,
        strength,
        now.isoformat(),
        expires_at
    ))
    conn.commit()
    conn.close()

def search_memory(
    user_id: str,
    query: str,
    scopes: Optional[List[str]] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    conn = _connect()
    c = conn.cursor()
    sql = "SELECT * FROM memories WHERE user_id=?"
    params: List[Any] = [user_id]
    if scopes:
        sql += " AND scope IN (%s)" % ",".join("?" * len(scopes))
        params += scopes
    if query:
        sql += " AND content LIKE ?"
        params.append(f"%{query}%")
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(top_k)
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    conn.close()
    return rows
