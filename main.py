# main.py
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import sqlite3
import os

# --- DB bootstrap ---
from utils.db import init_db, DB_PATH

# --- Create app first ---
app = FastAPI(title="Personal COO Backend Gateway", version="1.4.0")
init_db()

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include routers (Google OAuth) ---
# Make sure google_oauth.py defines: `router = APIRouter()` with /v1/oauth/google/* routes
from google_oauth import router as google_oauth_router
app.include_router(google_oauth_router)

# ----------------------------
# Health
# ----------------------------
@app.get("/v1/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

# ----------------------------
# Gmail endpoints
# ----------------------------
# Ensure gmail_api.py defines: list_threads, create_draft, send_message
from gmail_api import list_threads, create_draft, send_message

@app.post("/v1/gmail/thread-list")
async def gmail_thread_list(payload: Dict[str, Any]):
    q = payload.get("query", "in:inbox newer_than:7d -category:promotions")
    limit = int(payload.get("limit", 20))
    threads = list_threads(q, limit)
    return {"threads": threads}

@app.post("/v1/gmail/draft")
async def gmail_draft(payload: Dict[str, Any]):
    to = payload["to"]
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    thread_id = payload.get("threadId")
    draft = create_draft(to, subject, body, thread_id)
    return {"draft": draft}

@app.post("/v1/gmail/send")
async def gmail_send(payload: Dict[str, Any]):
    to = payload["to"]
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    thread_id = payload.get("threadId")
    sent = send_message(to, subject, body, thread_id)
    return {"sent": sent}

# Compatibility shims (optional): keep old names if your UI already calls them
@app.post("/v1/gmail/summarize-inbox")
async def gmail_summarize_inbox(payload: Dict[str, Any]):
    q = payload.get("query", "in:inbox newer_than:7d -category:promotions")
    limit = int(payload.get("max_threads", 10))
    threads = list_threads(q, limit)
    # Return as-is; summarization can be added later if needed
    return {"threads": threads}

@app.post("/v1/gmail/compose-and-send")
async def gmail_compose_and_send(payload: Dict[str, Any]):
    to = payload.get("to", [])
    subject = payload.get("subject", "")
    html_or_text = payload.get("html_body") or payload.get("body", "")
    thread_id = payload.get("threadId")
    draft_only = bool(payload.get("draftOnly", True))
    if not to:
        raise HTTPException(status_code=422, detail="'to' is required")
    # support string or list
    to_addr = to[0] if isinstance(to, list) else to
    if draft_only:
        draft = create_draft(to_addr, subject, html_or_text, thread_id)
        return {"status": "draft_created", "draft": draft}
    else:
        sent = send_message(to_addr, subject, html_or_text, thread_id)
        return {"status": "sent", "sent": sent}

# ----------------------------
# Odoo endpoints
# ----------------------------
# Ensure odoo_api.py defines: search_priority_items(days_ahead, limit, stages, owner_id) and debug_check()
from odoo_api import search_priority_items, debug_check

@app.post("/v1/odoo/priority-items/search")
async def odoo_priority(payload: Dict[str, Any]):
    days_ahead = int(payload.get("days_ahead", 14))
    limit = int(payload.get("limit", 10))
    stages = payload.get("stages")
    owner_id = payload.get("owner_id")
    return search_priority_items(days_ahead, limit, stages, owner_id)

@app.get("/v1/odoo/debug")
async def odoo_debug():
    return debug_check()

# ----------------------------
# Planner (your existing mock)
# ----------------------------
@app.post("/v1/planner/week-plan")
async def make_week_plan(payload: Dict[str, Any]):
    goals: List[str] = payload.get("goals", [])
    focus_minutes = payload.get("preferences", {}).get("focus_blocks_min", 90)
    tasks = []
    for i, g in enumerate(goals, start=1):
        deadline = (datetime.utcnow() + timedelta(days=3 + i)).date().isoformat()
        tasks.append({
            "id": f"task_{i:03d}",
            "title": g.strip()[:120],
            "owner": "Antonio",
            "priority": "P1" if i <= 3 else "P2",
            "impact": "RevenueCritical" if "close" in g.lower() or "deal" in g.lower() else None,
            "effort_min": focus_minutes,
            "deadline": deadline,
            "status": "open",
            "ext": {"odoo_id": None, "gmail_thread_id": None, "calendar_event_id": None}
        })
    subtasks = []
    for t in tasks:
        subtasks.extend([
            {"id": f"{t['id']}_1", "task_id": t["id"], "title": "Define scope", "estimate_minutes": int(0.3*focus_minutes), "due_date": t["deadline"], "status": "open"},
            {"id": f"{t['id']}_2", "task_id": t["id"], "title": "Draft first pass", "estimate_minutes": int(0.5*focus_minutes), "due_date": t["deadline"], "status": "open"},
            {"id": f"{t['id']}_3", "task_id": t["id"], "title": "Review & finalize", "estimate_minutes": int(0.2*focus_minutes), "due_date": t["deadline"], "status": "open"},
        ])
    schedule = []
    now = datetime.utcnow().replace(hour=15, minute=0, second=0, microsecond=0)
    for i, t in enumerate(tasks):
        start = now + timedelta(hours=i*2)
        schedule.append({
            "task_id": t["id"],
            "start": (start).isoformat() + "Z",
            "end": (start + timedelta(minutes=focus_minutes)).isoformat() + "Z",
            "timezone": "America/Mexico_City"
        })
    return {"tasks": tasks, "subtasks": subtasks, "schedule_suggestions": schedule}

# ----------------------------
# Memory (simple)
# ----------------------------
def _db():
    return sqlite3.connect(DB_PATH)

@app.post("/v1/memory/save")
async def memory_save(payload: Dict[str, Any] = Body(...)):
    """
    payload: { user_id, agent_id, scope, content, tags?, ttl_days?, source? }
    scope: 'short' | 'long' | 'team'
    """
    user_id = payload["user_id"]
    agent_id = payload.get("agent_id", "personal-coo")
    scope = payload.get("scope", "short")
    content = payload["content"]
    tags = ",".join(payload.get("tags", [])) if isinstance(payload.get("tags"), list) else payload.get("tags")
    ttl = payload.get("ttl_days")
    expires = (datetime.utcnow() + timedelta(days=int(ttl))).isoformat() if ttl else None
    source = payload.get("source", "manual")

    conn = _db(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS memories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, agent_id TEXT, scope TEXT, content TEXT, tags TEXT,
        source TEXT, score REAL DEFAULT 0, created_at TEXT, expires_at TEXT
    )""")
    c.execute("""INSERT INTO memories(user_id,agent_id,scope,content,tags,source,created_at,expires_at)
                 VALUES(?,?,?,?,?,?,?,?)""",
              (user_id, agent_id, scope, content, tags, source, datetime.utcnow().isoformat(), expires))
    conn.commit()
    rid = c.lastrowid
    conn.close()
    return {"id": rid, "status": "saved"}

@app.post("/v1/memory/search")
async def memory_search(payload: Dict[str, Any] = Body(...)):
    """
    payload: { user_id, agent_id?, scope?, q?, limit? }
    """
    user_id = payload["user_id"]
    agent_id = payload.get("agent_id", "personal-coo")
    scope = payload.get("scope")
    q = payload.get("q", "")
    limit = int(payload.get("limit", 20))

    conn = _db(); c = conn.cursor()
    base = "SELECT id, scope, content, tags, source, created_at, expires_at FROM memories WHERE user_id=? AND agent_id=?"
    args = [user_id, agent_id]
    if scope:
        base += " AND scope=?"; args.append(scope)
    if q:
        base += " AND content LIKE ?"; args.append(f"%{q}%")
    base += " ORDER BY created_at DESC LIMIT ?"; args.append(limit)

    rows = c.execute(base, args).fetchall()
    conn.close()
    return {"items": [
        {"id": r[0], "scope": r[1], "content": r[2], "tags": r[3], "source": r[4], "created_at": r[5], "expires_at": r[6]}
        for r in rows
    ]}

@app.get("/v1/memory/recent")
async def memory_recent(user_id: str, scope: Optional[str] = None, limit: int = 10):
    conn = _db(); c = conn.cursor()
    sql = "SELECT id, scope, content, tags, source, created_at FROM memories WHERE user_id=?"
    args = [user_id]
    if scope:
        sql += " AND scope=?"; args.append(scope)
    sql += " ORDER BY created_at DESC LIMIT ?"; args.append(limit)
    rows = c.execute(sql, args).fetchall()
    conn.close()
    return {"items": [
        {"id": r[0], "scope": r[1], "content": r[2], "tags": r[3], "source": r[4], "created_at": r[5]}
        for r in rows
    ]}

@app.delete("/v1/memory/{memory_id}")
async def memory_delete(memory_id: int):
    conn = _db(); c = conn.cursor()
    c.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    conn.commit()
    conn.close()
    return {"deleted": memory_id}
