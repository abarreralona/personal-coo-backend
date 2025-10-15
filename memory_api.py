
from typing import List, Dict, Any, Optional
from utils.db import write_memory, search_memory

def memory_write(user_id: str, kind: str, text: str, tags: Optional[List[str]]=None, strength: float=0.7):
    write_memory(user_id, kind, text, tags, strength)
    return {"status": "ok"}

def memory_search(user_id: str, query: str, kinds: Optional[List[str]]=None, top_k: int=5):
    rows = search_memory(user_id, query, kinds, top_k)
    for r in rows:
        r["tags"] = (r.get("tags") or "").split(",") if r.get("tags") else []
    return {"results": rows}
