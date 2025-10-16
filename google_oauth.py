# google_oauth.py
import os, json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from utils.db import upsert_token

router = APIRouter()

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
GOOGLE_REDIRECT_URI = os.environ["GOOGLE_REDIRECT_URI"]

# The scopes you use everywhere in your app (match your /start URL):
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]

def _flow():
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
    flow = _flow()
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # ensures refresh_token on re-connects
    )
    return RedirectResponse(auth_url)

@router.get("/v1/oauth/google/callback", response_class=HTMLResponse)
def google_oauth_callback(request: Request, state: str, code: str):
    flow = _flow()
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    flow.fetch_token(code=code)

    creds: Credentials = flow.credentials
    # Build what we store
    token_payload = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,  # may be None if not first consent
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
        "id_token": creds.id_token,  # may be None
    }
    expiry_iso = creds.expiry.isoformat() if creds.expiry else None
    scopes_str = " ".join(creds.scopes or [])

    user_id = "default"  # or read from your session/cookie if you support multi-user

    upsert_token(user_id, "google", token_payload, expiry_iso, scopes_str)

    return HTMLResponse("<h3>Google connected ✅</h3>You can close this window.")

