"""
IOlabs AI SDR Platform — Per-Client DB Session Router (Step 3)

get_session(client_id) returns an async SQLAlchemy session scoped
to the correct `client_{client_id}` PostgreSQL schema.

All platform-schema queries use a separate platform session.
Schema routing is enforced at the session level via search_path.
"""

# TODO: Step 3 — implement get_session(client_id), get_platform_session()
raise NotImplementedError("db/session.py: implemented in Step 3")
