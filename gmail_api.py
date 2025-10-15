
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
