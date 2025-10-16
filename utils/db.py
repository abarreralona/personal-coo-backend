import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

# Ruta persistente en Render (cámbiala con la env var DB_PATH si quieres)
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/coo_backend.db"))

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Habilita FK por si en el futuro las usamos
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """
    Crea tablas si no existen y asegura los índices/constraints necesarios
    para permitir ON CONFLICT(user_id, provider) DO UPDATE.
    """
    conn = _connect()
    c = conn.cursor()

    # ---- TOKENS ----
    # Guardamos los tokens OAuth por usuario y proveedor.
    # Clave única: (user_id, provider)
    c.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        user_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        access_token TEXT,
        refresh_token TEXT,
        token_json TEXT,      -- JSON completo del token (incluye expiry, etc.)
        scopes TEXT,          -- scopes separados por espacio (opcional)
        created_at TEXT,
        updated_at TEXT,
        UNIQUE(user_id, provider)
    );
    """)

    # Si la tabla existía sin UNIQUE, este índice la agrega sin romper datos
    c.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS ux_tokens_user_provider
    ON tokens(user_id, provider);
    """)

    # ---- MEMORIA ----
    c.execute("""
    CREATE TABLE IF NOT EXISTS mem_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        kind TEXT NOT NULL,       -- 'short' | 'long' | 'team' | etc
        text TEXT NOT NULL,
        tags TEXT,                -- csv de tags
        strength REAL DEFAULT 0.7,
        created_at TEXT
    );
    """)

    conn.commit()
    conn.close()

def upsert_token(
    user_id: str,
    provider: str,
    token_json: Dict[str, Any],
    scopes: Optional[List[str]] = None
) -> None:
    """
    Inserta/actualiza tokens. Requiere que exista UNIQUE(user_id, provider).
    """
    conn = _connect()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    access = token_json.get("access_token")
    refresh = token_json.get("refresh_token")
    scopes_str = " ".join(scopes or [])

    c.execute(
        """
        INSERT INTO tokens(user_id, provider, access_token, refresh_token, token_json, scopes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, provider) DO UPDATE SET
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            token_json=excluded.token_json,
            scopes=excluded.scopes,
            updated_at=excluded.updated_at
        """,
        (
            user_id,
            provider,
            access,
            refresh,
            json.dumps(token_json),
            scopes_str,
            now,
            now,
        ),
    )
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
    data = dict(row)
    if data.get("token_json"):
        try:
            data["token_json"] = json.loads(data["token_json"])
        except Exception:
            pass
    return data

def write_memory(
    user_id: str,
    kind: str,
    text: str,
    tags: Optional[List[str]] = None,
    strength: float = 0.7
):
    conn = _connect()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO mem_chunks(user_id, kind, text, tags, strength, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, kind, text, ",".join(tags or []), strength, now),
    )
    conn.commit()
    conn.close()

def search_memory(
    user_id: str,
    query: str,
    kinds: Optional[List[str]] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    conn = _connect()
    c = conn.cursor()
    base = "SELECT * FROM mem_chunks WHERE user_id=?"
    params: List[Any] = [user_id]
    if kinds:
        base += " AND kind IN (%s)" % ",".join("?" * len(kinds))
        params += kinds
    if query:
        base += " AND text LIKE ?"
        params.append(f"%{query}%")
    base += " ORDER BY created_at DESC LIMIT ?"
    params.append(top_k)
    rows = [dict(r) for r in c.execute(base, params).fetchall()]
    conn.close()
    return rows

