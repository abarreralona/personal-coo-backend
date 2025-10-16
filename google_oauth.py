# google_oauth.py
import os
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

# NOTE: keep these imports inside functions if you ever see import errors during build
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from utils.db import upsert_token

router = APIRouter()

# ---- Environment (fail fast with a readable message) ----
def _get_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing environment variable: {name}")
    return val

GOOGLE_CLIENT_ID = _get_env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _get_env("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = _get_env("GOOGLE_REDIRECT_URI")

# Scopes used across the app (Gmail + Calendar events)
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]

def _flow() -> Flow:
    """Create an OAuth Flow from env config."""
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
        scopes=OAUTH_SCOPES,
    )

@router.get("/v1/oauth/google/start")
def google_oauth_start():
    """
    Starts OAuth; redirects the user to Google's consent screen.
    """
    try:
        flow = _flow()
        flow.redirect_uri = GOOGLE_REDIRECT_URI
        auth_url, _state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",  # ensures refresh_token on reconnects
        )
        return RedirectResponse(auth_url)
    except Exception as e:
        return HTMLResponse(
            f"<h3>Google OAuth error</h3><pre>{e}</pre>"
            "<p>Check GOOGLE_CLIENT_ID / SECRET / REDIRECT_URI.</p>",
            status_code=500,
        )

@router.get("/v1/oauth/google/callback", response_class=HTMLResponse)
def google_oauth_callback(code: str, state: Optional[str] = None):
    """
    Handles the redirect from Google, exchanges code for tokens,
    and persists them in the tokens table (utils/db.py).
    """
    try:
        flow = _flow()
        flow.redirect_uri = GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)

        creds: Credentials = flow.credentials
        token_payload = {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,   # may be None if Google didn’t issue a new one
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
            "id_token": creds.id_token,             # may be None
        }
        expiry_iso = creds.expiry.isoformat() if creds.expiry else None
        scopes_str = " ".join(creds.scopes or [])

        # Single-user for now; swap to your real user_id if you support multiple
        upsert_token("default", "google", token_payload, expiry_iso, scopes_str)

        return HTMLResponse("<h3>Google connected ✅</h3><p>You can close this window.</p>")

    except Exception as e:
        return HTMLResponse(
            f"<h3>OAuth callback error</h3><pre>{e}</pre>"
            "<p>Common fixes:</p>"
            "<ul>"
            "<li>Authorized redirect URI in Google Cloud must match exactly:</li>"
            f"<li><code>{GOOGLE_REDIRECT_URI}</code></li>"
            "<li>.env/Render env vars must be set for CLIENT_ID/SECRET/REDIRECT_URI</li>"
            "<li>Scopes in /start and /callback must match</li>"
            "</ul>",
            status_code=500,
        )


