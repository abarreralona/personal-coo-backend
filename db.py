
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

DB_PATH = Path("coo_backend.db")

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
