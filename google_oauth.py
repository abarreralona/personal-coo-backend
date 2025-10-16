from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest

from utils.db import upsert_token as db_upsert_token, get_token as db_get_token

router = APIRouter()

# ----- Config -----
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "https://personal-coo-backend.onrender.com/v1/oauth/google/callback",
)

SCOPES: List[str] = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]


# ----- Helpers -----
def _build_flow() -> Flow:
    """Create an OAuth flow from env vars (no client_secret.json required)."""
    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )


def _save_tokens(creds: Credentials, scopes: List[str]) -> None:
    """Persist tokens in our SQLite table (scopes are required!)."""
    db_upsert_token(
        provider="google",
        access_token=creds.token or "",
        refresh_token=(getattr(creds, "refresh_token", "") or ""),
        token_expiry=(creds.expiry.isoformat() if getattr(creds, "expiry", None) else ""),
        scopes=" ".join(scopes),
    )


def stored_credentials() -> Optional[Credentials]:
    """Build Credentials from DB, if present."""
    row = db_get_token("google")
    if not row:
        return None

    scopes = (row.get("scopes") or "").split() if row.get("scopes") else SCOPES
    creds = Credentials(
        token=row.get("access_token") or "",
        refresh_token=row.get("refresh_token") or None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=scopes,
    )
    return creds


def refresh_access_token() -> Optional[Credentials]:
    """Refresh and re-save tokens if we have a refresh token."""
    creds = stored_credentials()
    if not creds:
        return None

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        _save_tokens(creds, creds.scopes or SCOPES)
    return creds


# ----- Routes -----
@router.get("/v1/oauth/google/start")
def google_oauth_start():
    """
    Starts Google's OAuth: returns a 307 redirect to Google's consent page.

    Note: Swagger's "Execute" will show "Failed to fetch" due to CORS on redirects.
    Open the URL in a new tab or visit it directly in your browser.
    """
    flow = _build_flow()
    auth_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(auth_url, status_code=307)


@router.get("/v1/oauth/google/callback", response_class=HTMLResponse)
def google_oauth_callback(request: Request):
    """
    Google redirects here with ?code=...&scope=...&state=...
    We exchange the code for tokens and persist them (including scopes).
    """
    try:
        flow = _build_flow()
        flow.fetch_token(authorization_response=str(request.url))
        creds: Credentials = flow.credentials

        # Google echoes scopes in the callback query param "scope" (space-separated)
        raw_scopes = request.query_params.get("scope", "")
        scopes = raw_scopes.split(" ") if raw_scopes else (creds.scopes or SCOPES)

        _save_tokens(creds, scopes)

        return HTMLResponse("<h3>Google connected ✅</h3><p>You can close this window.</p>")
    except Exception as e:
        msg = (
            "<h3>OAuth callback error</h3>"
            f"<pre>{e}</pre>"
            "<p><b>Common fixes:</b></p>"
            "<ul>"
            f"<li>Authorized redirect URI in Google Cloud must match exactly:<br>"
            f"<code>{GOOGLE_REDIRECT_URI}</code></li>"
            "<li>Render env vars set: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI</li>"
            "<li>Scopes in /start and /callback must match</li>"
            "</ul>"
        )
        return HTMLResponse(msg, status_code=500)

# --- Legacy compatibility for gmail_api.py -----------------------------------
def save_tokens(_owner: str, token_payload: dict) -> None:
    """
    Back-compat helper expected by gmail_api.py.
    Accepts a legacy dict and persists tokens to the oauth_tokens table.
    """
    # Handle both legacy and new field names
    access = token_payload.get("access_token") or token_payload.get("token") or ""
    refresh = token_payload.get("refresh_token") or ""
    expiry = (
        token_payload.get("token_expiry")
        or token_payload.get("expiry")  # may be datetime/str
        or ""
    )
    scopes = token_payload.get("scopes")

    # scopes may come as list/space-separated/None
    if isinstance(scopes, list):
        scopes = " ".join(scopes)
    elif not isinstance(scopes, str) or not scopes.strip():
        scopes = " ".join(SCOPES)

    # Persist using the canonical DB function
    db_upsert_token(
        provider="google",
        access_token=access,
        refresh_token=refresh,
        token_expiry=str(expiry) if expiry else "",
        scopes=scopes,
    )
# ----------------------------------------------------------------------------- 


