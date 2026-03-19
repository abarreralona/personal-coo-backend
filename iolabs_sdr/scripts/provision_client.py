"""
IOlabs AI SDR Platform — Client Provisioning Script (Step 5)

Usage:
  python scripts/provision_client.py <client_id>

Actions (all idempotent — safe to run multiple times):
  1. Create PostgreSQL schema: client_{client_id}
  2. Run all per-client table migrations (Section 7)
  3. Register client in platform.tenants (INSERT ... ON CONFLICT DO NOTHING)
  4. Create Redis rate limit keys for this client
  5. Verify: query all expected tables and confirm they exist

Exit codes:
  0 — success
  1 — client_id not provided or config file missing
  2 — DB connection failure
  3 — migration failure
"""

# TODO: Step 5 — implement provision_client() with full idempotency
raise NotImplementedError("scripts/provision_client.py: implemented in Step 5")
