from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

app = FastAPI(title="Personal COO Backend Gateway", version="1.0.0")

# --- CORS (adjust origins for your Lovable/Manus domains) ---
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

@app.post("/v1/planner/week-plan")
async def make_week_plan(payload: Dict[str, Any]):
    goals: List[str] = payload.get("goals", [])
    focus_minutes = payload.get("preferences", {}).get("focus_blocks_min", 90)
    # Produce a tiny deterministic mock plan you can immediately render in Lovable
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

# --- Placeholders for other routes you will fill later ---
@app.post("/v1/gmail/summarize-inbox")
async def gmail_summarize_inbox(payload: Dict[str, Any]):
    query = payload.get("query", "in:inbox newer_than:7d -category:promotions")
    return {"threads": [
        {"threadId": "abc123", "subject": "Sigma – next steps", "from": "sigma@example.com",
         "last_message_ts": datetime.utcnow().isoformat() + "Z",
         "snippet": "Checking in on the SOW...",
         "action_needed": True, "suggested_reply": "Thanks for the update — attaching the SOW for your review."}
    ]}

@app.post("/v1/gmail/compose-and-send")
async def gmail_compose_and_send(payload: Dict[str, Any]):
    # This is a mock implementation for first deploy.
    draft_only = payload.get("draftOnly", True)
    status = "draft_created" if draft_only else "sent"
    return {"message_id": "mock-msg-001", "threadId": payload.get("threadId", "abc123"), "status": status}

@app.post("/v1/calendar/block-time")
async def calendar_block_time(payload: Dict[str, Any]):
    # Mock create event
    start = payload.get("start")
    end = payload.get("end")
    if not (start and end):
        raise HTTPException(status_code=422, detail="start and end are required")
    return {"event_id": "evt_001", "html_link": "https://calendar.google.com/event?eid=mock", "start": start, "end": end, "timezone": payload.get("timezone", "UTC")}
