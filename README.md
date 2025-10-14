# Personal COO Backend Gateway

FastAPI backend for your Lovable + Manus agent. This minimal server gives you:
- `GET /v1/health` — health check
- `POST /v1/planner/week-plan` — returns a mock plan from given goals
- `POST /v1/gmail/summarize-inbox` — mock inbox summary
- `POST /v1/gmail/compose-and-send` — mock draft/send
- `POST /v1/calendar/block-time` — mock calendar event

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

Open http://localhost:8080/v1/health

## Deploy on Render
1. Push these files to GitHub (repo name suggestion: `personal-coo-backend`).
2. On Render → New → Web Service → connect the repo.
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn main:app --host 0.0.0.0 --port 8080`
5. Add env vars from `.env.example` (use real values in Render UI).
