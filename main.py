from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# NEW imports
from utils.db import init_db
from google_oauth import oauth_start_url, exchange_code_for_tokens, save_tokens
from gmail_api import summarize_inbox, send_email
from odoo_api import search_priority_items
from memory_api import memory_write, memory_search

init_db()

app = FastAPI(title="Personal COO Backend Gateway", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/v1/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

# ---------- Google OAuth ----------
@app.get("/v1/oauth/google/start")
async def google_oauth_start(user_id: str = "default"):
    return RedirectResponse(oauth_start_url(user_id=user_id))

@app.get("/v1/oauth/google/callback")
async def google_oauth_callback(code: str, state: Optional[str] = None):
    tokens = exchange_code_for_tokens(code)
    save_tokens("default", tokens)
    return HTMLResponse("<h2>Google connected ✅</h2><p>You can close this window.</p>")

# ---------- Gmail (real) ----------
@app.post("/v1/gmail/summarize-inbox")
async def gmail_summarize(payload: Dict[str, Any]):
    user_id = payload.get("user_id", "default")
    query = payload.get("query", "in:inbox newer_than:7d -category:promotions")
    max_threads = int(payload.get("max_threads", 10))
    return {"threads": summarize_inbox(user_id, query, max_threads)}

@app.post("/v1/gmail/compose-and-send")
async def gmail_compose_send(payload: Dict[str, Any]):
    user_id = payload.get("user_id", "default")
    to = payload.get("to", [])
    subject = payload.get("subject", "")
    html_body = payload.get("html_body", "")
    threadId = payload.get("threadId")
    draftOnly = bool(payload.get("draftOnly", True))
    return send_email(user_id, to, subject, html_body, threadId, draftOnly)

# ---------- Odoo ----------
@app.post("/v1/odoo/priority-items/search")
async def odoo_priority(payload: Dict[str, Any]):
    days_ahead = int(payload.get("days_ahead", 14))
    limit = int(payload.get("limit", 10))
    stages = payload.get("stages")
    owner_id = payload.get("owner_id")
    return search_priority_items(days_ahead, limit, stages, owner_id)
    from odoo_api import search_priority_items, debug_check  # make sure debug_check is imported

@app.get("/v1/odoo/debug")
async def odoo_debug():
    return debug_check()
    from odoo_api import search_priority_items, debug_check  # make sure this import is present

@app.get("/v1/odoo/debug")
async def odoo_debug():
    return debug_check()


# ---------- Memory ----------
@app.post("/v1/memory/write")
async def memory_write_route(payload: Dict[str, Any]):
    return memory_write(payload.get("user_id","default"),
                        payload["kind"], payload["text"],
                        payload.get("tags"), float(payload.get("strength", 0.7)))

@app.post("/v1/memory/search")
async def memory_search_route(payload: Dict[str, Any]):
    return memory_search(payload.get("user_id","default"),
                         payload.get("query",""),
                         payload.get("kinds"), int(payload.get("top_k",5)))

# ---------- Your existing planner ----------
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
