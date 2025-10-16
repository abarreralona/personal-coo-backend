
import os
import xmlrpc.client

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USER = os.getenv("ODOO_USER")
ODOO_API_KEY = os.getenv("ODOO_API_KEY")

def _get_client():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_API_KEY, {})
    if not uid:
        raise RuntimeError("Odoo auth failed. Check credentials/env vars.")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models

def search_priority_items(days_ahead: int=14, limit: int=10, stages=None, owner_id=None):
    uid, models = _get_client()
    domain = [["type","=","opportunity"]]
    if stages:
        domain.append(["stage_id.name","in", stages])
    fields = ["id","name","stage_id","probability","expected_revenue","activity_summary","user_id","date_deadline"]
    leads = models.execute_kw(ODOO_DB, uid, ODOO_API_KEY,
                              "crm.lead", "search_read",
                              [domain], {"fields": fields, "limit": limit, "order":"probability desc"})
    items = []
    for l in leads:
        items.append({
            "lead_id": l["id"],
            "name": l["name"],
            "stage": l["stage_id"][1] if isinstance(l["stage_id"], list) else l["stage_id"],
            "probability": (l.get("probability") or 0)/100.0,
            "deadline": l.get("date_deadline"),
            "expected_revenue": l.get("expected_revenue") or 0,
            "activity_summary": l.get("activity_summary"),
            "owner_id": l["user_id"][0] if isinstance(l.get("user_id"), list) else None
        })
    return {"items": items}

def debug_check():
    import os, xmlrpc.client
    url = os.getenv("ODOO_URL")
    db = os.getenv("ODOO_DB")
    user = os.getenv("ODOO_USER")
    # don't return API key in the response!

    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        ver = common.version()            # no auth needed; checks URL reachability
    except Exception as e:
        return {"ok": False, "phase": "version", "error": str(e), "url": url, "db": db, "user": user}

    try:
        uid = common.authenticate(db, user, os.getenv("ODOO_API_KEY"), {})
    except Exception as e:
        return {"ok": False, "phase": "authenticate", "error": str(e), "url": url, "db": db, "user": user, "version": ver}

    return {
        "ok": bool(uid),
        "phase": "done",
        "uid": uid,
        "version": ver,
        "url": url,
        "db": db,
        "user": user
    }
