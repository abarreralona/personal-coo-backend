import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

DB_PATH = Path(os.getenv("DB_PATH", "/var/data/coo_backend.db"))

def _connect():
    # isolation_level=None => autocommit off; we’ll commit manually
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Ensure all required tables exist with the correct schema.
    Also performs a light migration of oauth_tokens if needed.
    """
    conn = _connect()
    c = conn.cursor()

    # --- OAuth tokens table (correct schema) ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        access_token TEXT,
        refresh_token TEXT,
        token_expiry TEXT,
        scopes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, provider)
    )
    """)

    # --- Memory tables (unchanged) ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        scope TEXT NOT NULL,        -- 'short' | 'long' | 'team'
        content TEXT NOT NULL,
        tags TEXT,
        source TEXT,                 -- 'manual' | 'gmail' | 'odoo' | 'chat'
        score REAL DEFAULT 0,
        created_at TEXT NOT NULL,
        expires_at TEXT
    )
    """)

    # Legacy tables that might exist in older versions:
    # - tokens (user_id PK) with token_json
    # - mem_chunks
    # Try to migrate what’s useful into the current schema.

    # If legacy `tokens` exists, pull Google token_json and move it over (best-effort).
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tokens'")
    if c.fetchone():
        try:
            rows = c.execute("SELECT user_id, provider, token_json FROM tokens").fetchall()
            for r in rows:
                user_id = r["user_id"]
                provider = r["provider"]
                try:
                    payload = json.loads(r["token_json"] or "{}")
                except Exception:
                    payload = {}
                upsert_token(user_id=user_id,
                             provider=provider or "google",
                             access_token=payload.get("access_token"),
                             refresh_token=payload.get("refresh_token"),
                             token_expiry=payload.get("expiry") or payload.get("token_expiry"),
                             scopes=",".join(payload.get("scopes", [])) if isinstance(payload.get("scopes"), list) else (payload.get("scopes") or ""))
        except Exception:
            # best-effort; ignore if structure doesn’t match
            pass

    conn.commit()
    conn.close()

def upsert_token(
    user_id: str,
    provider: str,
    access_token: Optional[str],
    refresh_token: Optional[str],
    token_expiry: Optional[str],
    scopes: Optional[str]
):
    """
    UPSERT by (user_id, provider). Requires UNIQUE(user_id, provider).
    """
    conn = _connect()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    c.execute("""
        INSERT INTO oauth_tokens (user_id, provider, access_token, refresh_token, token_expiry, scopes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, provider) DO UPDATE SET
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            token_expiry=excluded.token_expiry,
            scopes=excluded.scopes,
            updated_at=excluded.updated_at
    """, (user_id, provider, access_token, refresh_token, token_expiry, scopes or "", now, now))

    conn.commit()
    conn.close()

def get_token(user_id: str, provider: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    c = conn.cursor()
    row = c.execute("""
        SELECT user_id, provider, access_token, refresh_token, token_expiry, scopes, created_at, updated_at
        FROM oauth_tokens
        WHERE user_id=? AND provider=?
    """, (user_id, provider)).fetchone()
    conn.close()
    return dict(row) if row else None

# -------- Optional: simple memory helpers (unchanged API) --------

def write_memory(user_id: str, kind: str, text: str, tags: Optional[List[str]]=None,
                 strength: float=0.7, agent_id: str="personal-coo", scope: str="long",
                 source: str="manual", expires_at: Optional[str]=None):
    conn = _connect()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO memories (user_id, agent_id, scope, content, tags, source, score, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, agent_id, scope, text, ",".join(tags or []), source, float(strength), now, expires_at))
    conn.commit()
    conn.close()

def search_memory(user_id: str, query: str, scopes: Optional[List[str]]=None, top_k: int=5):
    conn = _connect()
    c = conn.cursor()
    sql = "SELECT * FROM memories WHERE user_id=?"
    params: List[Any] = [user_id]
    if scopes:
        sql += " AND scope IN ({})".format(",".join("?"*len(scopes)))
        params += scopes
    if query:
        sql += " AND content LIKE ?"
        params.append(f"%{query}%")
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(top_k)
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    conn.close()
    return rows

