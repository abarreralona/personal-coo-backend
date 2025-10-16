import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

# Use the Render persistent disk if available, otherwise fallback to local path
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/coo_backend.db"))

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _connect()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        user_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        access_token TEXT,
        refresh_token TEXT,
        token_json TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS mem_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        text TEXT NOT NULL,
        tags TEXT,
        strength REAL DEFAULT 0.7,
        created_at TEXT
    );
    """)
    conn.commit()
    conn.close()

def upsert_token(user_id: str, provider: str, token_json: Dict[str, Any]):
    conn = _connect()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO tokens(user_id, provider, access_token, refresh_token, token_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            token_json=excluded.token_json,
            updated_at=excluded.updated_at
    """, (user_id, provider, token_json.get("access_token"), token_json.get("refresh_token"),
          json.dumps(token_json), now, now))
    conn.commit()
    conn.close()

def get_token(user_id: str, provider: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    c = conn.cursor()
    row = c.execute("SELECT * FROM tokens WHERE user_id=? AND provider=?", (user_id, provider)).fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    if data.get("token_json"):
        data["token_json"] = json.loads(data["token_json"])
    return data

def write_memory(user_id: str, kind: str, text: str, tags: Optional[List[str]]=None, strength: float=0.7):
    conn = _connect()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO mem_chunks(user_id, kind, text, tags, strength, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, kind, text, ",".join(tags or []), strength, now))
    conn.commit()
    conn.close()

def search_memory(user_id: str, query: str, kinds: Optional[List[str]]=None, top_k: int=5):
    conn = _connect()
    c = conn.cursor()
    base = "SELECT * FROM mem_chunks WHERE user_id=?"
    params = [user_id]
    if kinds:
        base += " AND kind IN (%s)" % ",".join("?"*len(kinds))
        params += kinds
    if query:
        base += " AND text LIKE ?"
        params.append(f"%{query}%")
    base += " ORDER BY created_at DESC LIMIT ?"
    params.append(top_k)
    rows = [dict(r) for r in c.execute(base, params).fetchall()]
    conn.close()
    return rows

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # where we store OAuth tokens (if you don’t have it already)
    c.execute("""
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        provider TEXT PRIMARY KEY,
        access_token TEXT,
        refresh_token TEXT,
        token_expiry TEXT,
        scopes TEXT
    )
    """)

    # memory table
    c.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,           -- e.g. your Google email (owner of the agent)
        agent_id TEXT NOT NULL,          -- e.g. 'personal-coo'
        scope TEXT NOT NULL,             -- 'short' | 'long' | 'team'
        content TEXT NOT NULL,
        tags TEXT,                       -- comma-separated tags ("sales,weekly-plan")
        source TEXT,                     -- 'manual' | 'gmail' | 'odoo' | 'chat'
        score REAL DEFAULT 0,            -- optional ranking field
        created_at TEXT NOT NULL,
        expires_at TEXT                   -- null for long-term
    )
    """)

    conn.commit()
    conn.close()

def get_token(provider: str):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    row = c.execute("SELECT access_token, refresh_token, token_expiry, scopes FROM oauth_tokens WHERE provider=?", (provider,)).fetchone()
    conn.close()
    if not row: return None
    return {"access_token": row[0], "refresh_token": row[1], "token_expiry": row[2], "scopes": row[3]}

def upsert_token(provider: str, access_token: str, refresh_token: str, token_expiry: str, scopes: str):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""INSERT INTO oauth_tokens(provider, access_token, refresh_token, token_expiry, scopes)
                 VALUES(?,?,?,?,?)
                 ON CONFLICT(provider) DO UPDATE SET
                    access_token=excluded.access_token,
                    refresh_token=excluded.refresh_token,
                    token_expiry=excluded.token_expiry,
                    scopes=excluded.scopes""",
              (provider, access_token, refresh_token, token_expiry, scopes))
    conn.commit(); conn.close()

