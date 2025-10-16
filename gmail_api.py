
import requests
from typing import Dict, Any, List, Optional
from utils.db import get_token
from google_oauth import refresh_access_token, save_tokens

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"

def _auth_header(access_token: str):
    return {"Authorization": f"Bearer {access_token}"}

def _ensure_fresh_token(user_id: str) -> str:
    t = get_token(user_id, "google")
    if not t: raise RuntimeError("No Google tokens saved for user")
    tok = t["token_json"]
    access = tok.get("access_token")
    if not access and tok.get("refresh_token"):
        newtok = refresh_access_token(tok["refresh_token"])
        newtok["refresh_token"] = tok["refresh_token"]
        save_tokens(user_id, newtok)
        access = newtok["access_token"]
    return access

def summarize_inbox(user_id: str, query: str, max_threads: int=10) -> List[Dict[str, Any]]:
    access = _ensure_fresh_token(user_id)
    params = {"q": query, "maxResults": max_threads}
    r = requests.get(f"{GMAIL_API}/users/me/threads", headers=_auth_header(access), params=params, timeout=30)
    r.raise_for_status()
    items = r.json().get("threads", [])

    summaries = []
    for it in items:
        tid = it["id"]
        tr = requests.get(f"{GMAIL_API}/users/me/threads/{tid}", headers=_auth_header(access), timeout=30)
        tr.raise_for_status()
        data = tr.json()
        headers = {h['name'].lower(): h['value'] for h in data['messages'][-1]['payload']['headers']}
        summaries.append({
            "threadId": tid,
            "subject": headers.get("subject", ""),
            "from": headers.get("from",""),
            "last_message_ts": data['messages'][-1]['internalDate'],
            "snippet": data.get("snippet",""),
            "action_needed": True if "?" in data.get("snippet","") else False,
            "suggested_reply": None
        })
    return summaries

def send_email(user_id: str, to: List[str], subject: str, html_body: str, threadId: Optional[str]=None, draftOnly: bool=True):
    import base64
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    access = _ensure_fresh_token(user_id)

    msg = MIMEMultipart("alternative")
    msg["to"] = ", ".join(to)
    msg["subject"] = subject
    msg.attach(MIMEText(html_body, "html"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    if draftOnly:
        payload = {"message": {"raw": raw}}
        if threadId:
            payload["message"]["threadId"] = threadId
        r = requests.post(f"{GMAIL_API}/users/me/drafts", headers=_auth_header(access), json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        return {"message_id": data.get("id"), "threadId": threadId or data.get("message",{}).get("threadId"), "status": "draft_created"}
    else:
        payload = {"raw": raw}
        if threadId:
            payload["threadId"] = threadId
        r = requests.post(f"{GMAIL_API}/users/me/messages/send", headers=_auth_header(access), json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        return {"message_id": data.get("id"), "threadId": data.get("threadId"), "status": "sent"}

import base64, json, time
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional
from utils.db import get_token, upsert_token
import google.oauth2.credentials
import googleapiclient.discovery
import requests

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

def _build_service() -> googleapiclient.discovery.Resource:
    tok = get_token("google")
    if not tok: raise RuntimeError("Google account not connected")

    # refresh if needed (simple check 60s skew)
    exp_ts = int(json.loads(tok["token_expiry"])) if tok["token_expiry"] else 0
    if exp_ts and time.time() > exp_ts - 60:
        data = {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "refresh_token": tok["refresh_token"],
            "grant_type": "refresh_token",
        }
        r = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=20)
        r.raise_for_status()
        nd = r.json()
        # store new access + new expiry
        new_exp = int(time.time()) + int(nd["expires_in"])
        upsert_token("google", nd["access_token"], tok["refresh_token"], json.dumps(new_exp), tok["scopes"])
        tok = get_token("google")

    creds = google.oauth2.credentials.Credentials(
        token=tok["access_token"],
        refresh_token=tok["refresh_token"],
        token_uri=GOOGLE_TOKEN_URL,
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=json.loads(tok["scopes"]) if tok["scopes"] else ["https://www.googleapis.com/auth/gmail.modify"]
    )
    return googleapiclient.discovery.build("gmail", "v1", credentials=creds, cache_discovery=False)

def list_threads(query: str, max_results: int = 20):
    svc = _build_service()
    res = svc.users().threads().list(userId="me", q=query, maxResults=max_results).execute()
    return res.get("threads", [])

def get_thread(thread_id: str):
    svc = _build_service()
    return svc.users().threads().get(userId="me", id=thread_id, format="metadata").execute()

def _create_message(to: str, subject: str, body: str) -> Dict[str, Any]:
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return {"raw": raw}

def create_draft(to: str, subject: str, body: str, thread_id: Optional[str] = None):
    svc = _build_service()
    message = _create_message(to, subject, body)
    if thread_id:
        message["threadId"] = thread_id
    draft = svc.users().drafts().create(userId="me", body={"message": message}).execute()
    return draft

def send_message(to: str, subject: str, body: str, thread_id: Optional[str] = None):
    svc = _build_service()
    message = _create_message(to, subject, body)
    if thread_id:
        message["threadId"] = thread_id
    sent = svc.users().messages().send(userId="me", body=message).execute()
    return sent
# move heavy imports inside functions
def _google_creds_from_store(user_id: str):
    try:
        from google.oauth2.credentials import Credentials
    except Exception as e:
        raise RuntimeError("Google libs missing. Did you add google-* packages to requirements.txt?") from e
    # ...rest...

def summarize_inbox(payload):
    try:
        from googleapiclient.discovery import build
    except Exception as e:
        raise RuntimeError("Google API client not installed.") from e
    # ...rest...

def send_email(payload):
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except Exception as e:
        raise RuntimeError("Google API client not installed.") from e
    # ...rest...
