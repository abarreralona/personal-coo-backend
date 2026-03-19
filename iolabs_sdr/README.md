# IOlabs AI SDR Platform

Fully automated, multi-tenant outbound sales development system for mid-market manufacturing companies.

> **Agency model** — IOlabs operates one infrastructure instance on behalf of 6–15 client companies, each fully isolated.

## Architecture

| System | Role |
|--------|------|
| **AI SDR Agent** | Executes the full outbound pipeline (5 stages) |
| **Open Claw** | Strategic orchestrator — commands campaigns across geographies |
| **Mirror Fish** | On-demand copy simulation engine against synthetic buyer personas |

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- PostgreSQL 15+ with `pgvector` extension
- Redis 7+
- Anthropic API key
- SerpAPI key

## Quick Start

```bash
# 1. Clone repo and enter the iolabs_sdr directory
cd iolabs_sdr

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your actual credentials

# 3. Start all services
docker compose up -d

# 4. Provision a new client
python scripts/provision_client.py client_example

# 5. Trigger manual discovery (after provisioning)
curl -X POST http://localhost:8000/api/trigger/discovery?client_id=client_example \
  -H "X-Api-Key: $API_SECRET_KEY"
```

## Provisioning a New Client

1. Copy `configs/client_example.json` → `configs/{client_id}.json`
2. Fill in all config fields (see Section 4 of spec)
3. Set SMTP password env var: `SMTP_PASSWORD_{CLIENT_ID_UPPER}=...`
4. Run: `python scripts/provision_client.py {client_id}`
5. Verify: `GET /api/clients/{client_id}/status`

Provisioning is **idempotent** — safe to run multiple times.

## Triggering Manual Discovery

```bash
POST /api/trigger/discovery?client_id={client_id}
X-Api-Key: {API_SECRET_KEY}
```

## Queue Monitoring

```bash
# Check queue depths
celery -A core.celery_app inspect active_queues

# Check all workers
celery -A core.celery_app status

# Platform health API
GET /api/health
```

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v

# Integration tests (requires running PostgreSQL + Redis)
pytest tests/test_pipeline_integration.py -v -m integration
```

## Open Items (Must Resolve Before Mirror Fish)

| # | Item | Status |
|---|------|--------|
| 1 | Email Methodology Rules 6–10 | **PENDING — IOlabs operator** |
| 2 | Mirror Fish seed file: `packaging_distribution_midmarket` | **PENDING — IOlabs operator** |
| 3 | Email 2 and Email 3 templates (all 6 personas) | **PENDING — IOlabs operator** |
| 4 | LinkedIn persona reply prompts | **PENDING — IOlabs operator** |
| 5 | Anomaly threshold confirmation (open_rate/bounce_rate) | **PENDING — confirm** |
| 6 | SDR handoff notification format | **PENDING — IOlabs operator** |

## Build Status (Phase 1)

| Step | Component | Status |
|------|-----------|--------|
| 1 | Project Scaffold | ✅ Complete |
| 2 | Config Loader | ⬜ Pending |
| 3 | DB Models & Session | ⬜ Pending |
| 4 | Celery App & Rate Limiter | ⬜ Pending |
| 5 | Client Provisioning | ⬜ Pending |
| 6 | Stage 1: Discovery | ⬜ Pending |
| 7 | Keyword Scanner & Scorer | ⬜ Pending |
| 8 | Visual Classifier | ⬜ Pending |
| 9 | LLM Pickup & Signal Engine | ⬜ Pending |
| 10 | Stage 2: Classification | ⬜ Pending |
| 11 | Stage 3: Enrichment | ⬜ Pending |
| 12 | Email Composer | ⬜ Pending |
| 13 | Email Sender | ⬜ Pending |
| 14 | FastAPI Webhooks | ⬜ Pending |
| 15 | Reply Detector | ⬜ Pending |
| 16 | Reply Responder & Notifier | ⬜ Pending |
| 17 | LinkedIn Workers | ⬜ Pending |
| 18 | Full Integration Test | ⬜ Pending |
| 19 | Documentation & Docker | ⬜ Pending |
