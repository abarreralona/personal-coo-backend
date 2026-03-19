"""
IOlabs AI SDR Platform — Hot-Reload Client Config (Step 5)

Usage:
  python scripts/reload_config.py <client_id>

Reloads client config JSON without restarting workers.
Publishes a Redis message that workers subscribe to for live config refresh.
Validates the new config before publishing (fails gracefully with error message).
"""

# TODO: Step 5 — implement reload_config() with Redis pub/sub notification
raise NotImplementedError("scripts/reload_config.py: implemented in Step 5")
