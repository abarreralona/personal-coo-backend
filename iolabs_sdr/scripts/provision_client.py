"""
IOlabs AI SDR Platform — Client Provisioning Script (Step 5)

Usage:
  python scripts/provision_client.py <client_id>

Actions (all idempotent — safe to run multiple times):
  1. Validate client_id format and load config to confirm it exists
  2. Run platform Alembic migration (001) — creates platform schema + tables
  3. Run per-client Alembic migration (002) — creates client_{id} schema + tables
  4. Register client in platform.tenants (INSERT ... ON CONFLICT DO NOTHING)
  5. Verify Redis is reachable (rate limiter will use it at send time)
  6. Verify all 7 expected client tables exist
  7. Print CELERY_QUEUES_* update instructions

Exit codes:
  0 — success
  1 — client_id not provided or config file missing / invalid
  2 — DB connection failure
  3 — migration failure
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg2

from iolabs_sdr.core.config_loader import load_client_config
from iolabs_sdr.core.rate_limiter import RateLimiter

# ── Exit codes ─────────────────────────────────────────────────────────────────

EXIT_OK = 0
EXIT_BAD_ARGS = 1
EXIT_DB_FAILURE = 2
EXIT_MIGRATION_FAILURE = 3

# ── Constants ──────────────────────────────────────────────────────────────────

_SAFE_CLIENT_ID_RE = re.compile(r"^[a-z0-9_]+$")

# All 7 per-client tables that migration 002 creates
CLIENT_TABLES = [
    "leads",
    "contacts",
    "emails_sent",
    "email_replies",
    "linkedin_messages",
    "dnc_list",
    "sequence_schedule",
]

# All 6 Celery pipeline stages (for CELERY_QUEUES_* instructions)
PIPELINE_STAGES = ["discovery", "classify", "enrich", "email", "reply", "linkedin"]

# Path helpers (resolved relative to this file so the script works from any CWD)
_SCRIPTS_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent          # iolabs_sdr/
_ALEMBIC_INI = _PROJECT_ROOT / "alembic.ini"
_CONFIGS_DIR = _PROJECT_ROOT / "configs"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _psycopg2_url(database_url: str) -> str:
    """Strip the asyncpg driver prefix so psycopg2 can parse the URL."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _run_alembic(args: list[str]) -> subprocess.CompletedProcess:
    """
    Run alembic with the project's alembic.ini.
    Always uses the python interpreter from the current venv so the
    iolabs_sdr package is importable inside the migration env.py.
    """
    cmd = [sys.executable, "-m", "alembic", "-c", str(_ALEMBIC_INI)] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def _verify_tables(cur, schema: str) -> list[str]:
    """
    Check all expected client tables exist in schema.
    Returns a list of missing table names (empty = all present).
    """
    missing = []
    for table in CLIENT_TABLES:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
            """,
            (schema, table),
        )
        if not cur.fetchone()[0]:
            missing.append(table)
    return missing


def _print_queue_instructions(client_id: str) -> None:
    """Print the CELERY_QUEUES_* env var update instructions."""
    print()
    print("─" * 60)
    print("Next step — add this client's queues to your .env file:")
    print("─" * 60)
    for stage in PIPELINE_STAGES:
        var = f"CELERY_QUEUES_{stage.upper()}"
        queue = f"{client_id}_{stage}"
        print(f"  Append '{queue}' to {var}")
    print()
    print("Then restart your Celery workers to pick up the new queues.")
    print("─" * 60)


# ── Main ───────────────────────────────────────────────────────────────────────


def provision_client(client_id: str) -> int:
    """
    Provision a new (or re-provision an existing) client.

    Returns an exit code (0 = success).
    """
    # ── Step 1: validate client_id ────────────────────────────────────────────
    if not _SAFE_CLIENT_ID_RE.match(client_id):
        print(
            f"[provision] ERROR: client_id '{client_id}' must be "
            "lowercase alphanumeric + underscores only.",
            file=sys.stderr,
        )
        return EXIT_BAD_ARGS

    schema = f"client_{client_id}"
    config_path = _CONFIGS_DIR / f"{client_id}.json"

    if not config_path.exists():
        print(
            f"[provision] ERROR: Config file not found: {config_path}\n"
            f"Create {config_path} before provisioning.",
            file=sys.stderr,
        )
        return EXIT_BAD_ARGS

    # Load + validate the config (catches malformed JSON / missing fields early)
    try:
        config = load_client_config(client_id, _CONFIGS_DIR)
        print(f"[provision] Config loaded OK for client '{config.client_id}'.")
    except Exception as exc:
        print(f"[provision] ERROR: Config validation failed: {exc}", file=sys.stderr)
        return EXIT_BAD_ARGS

    # ── Step 2: connect to DB ─────────────────────────────────────────────────
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://iolabs:changeme@localhost:5432/iolabs_sdr",
    )
    try:
        conn = psycopg2.connect(_psycopg2_url(database_url))
        conn.autocommit = True
        cur = conn.cursor()
        print("[provision] DB connection OK.")
    except Exception as exc:
        print(f"[provision] ERROR: DB connection failed: {exc}", file=sys.stderr)
        return EXIT_DB_FAILURE

    # ── Step 3: run platform migration (001) ──────────────────────────────────
    print("[provision] Running platform migration (001)…")
    result = _run_alembic(["upgrade", "001"])
    if result.returncode != 0:
        print(
            f"[provision] ERROR: Platform migration failed:\n{result.stderr}",
            file=sys.stderr,
        )
        cur.close()
        conn.close()
        return EXIT_MIGRATION_FAILURE
    print("[provision] Platform migration OK (idempotent — skipped if already applied).")

    # ── Step 4: run per-client migration (002) ────────────────────────────────
    print(f"[provision] Running per-client migration (002) for schema '{schema}'…")
    result = _run_alembic(["upgrade", "002", "-x", f"client_schema={schema}"])
    if result.returncode != 0:
        print(
            f"[provision] ERROR: Per-client migration failed:\n{result.stderr}",
            file=sys.stderr,
        )
        cur.close()
        conn.close()
        return EXIT_MIGRATION_FAILURE
    print(f"[provision] Per-client migration OK (idempotent — skipped if already applied).")

    # ── Step 5: register in platform.tenants ─────────────────────────────────
    print(f"[provision] Registering '{client_id}' in platform.tenants…")
    cur.execute(
        """
        INSERT INTO platform.tenants (client_id, name, config_path, db_schema, active)
        VALUES (%s, %s, %s, %s, true)
        ON CONFLICT (client_id) DO NOTHING
        """,
        (client_id, config.sender_name, str(config_path), schema),
    )
    print(f"[provision] Tenant registration OK (INSERT ... ON CONFLICT DO NOTHING).")

    # ── Step 6: Redis reachability check ─────────────────────────────────────
    try:
        limiter = RateLimiter()
        if limiter.ping():
            print("[provision] Redis reachable — rate limiter ready.")
        else:
            print(
                "[provision] WARNING: Redis ping returned False. "
                "Rate limiter (BR2/BR3) will fail at send time. "
                "Verify REDIS_URL and that Redis is running.",
                file=sys.stderr,
            )
    except Exception as exc:
        print(
            f"[provision] WARNING: Could not reach Redis: {exc}. "
            "Continuing — Redis is only required at email send time.",
            file=sys.stderr,
        )

    # ── Step 7: verify all 7 client tables ───────────────────────────────────
    print(f"[provision] Verifying client tables in schema '{schema}'…")
    missing = _verify_tables(cur, schema)
    if missing:
        print(
            f"[provision] ERROR: Expected tables not found in '{schema}': "
            + ", ".join(missing),
            file=sys.stderr,
        )
        cur.close()
        conn.close()
        return EXIT_DB_FAILURE

    for table in CLIENT_TABLES:
        print(f"  ✓ {schema}.{table}")

    cur.close()
    conn.close()

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"\n[provision] Client '{client_id}' provisioned successfully.")
    _print_queue_instructions(client_id)
    return EXIT_OK


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/provision_client.py <client_id>",
            file=sys.stderr,
        )
        sys.exit(EXIT_BAD_ARGS)

    client_id = sys.argv[1].strip()
    sys.exit(provision_client(client_id))


if __name__ == "__main__":
    main()
