"""
Redis-backed conversation storage.

Key schema
----------
conversation:<user_id>:<conversation_id>   STRING (JSON blob) — the full
    conversation: {id, user_id, pool, title, created_at, updated_at, messages}
conversation_index:<user_id>               ZSET — member=conversation_id,
    score=last-touched unix time. Lets ``list_conversations`` return newest-
    first without a KEYS/SCAN over the user's conversation keys.

A conversation's ``messages`` list holds every turn as plain dicts:
    {"role": "user"|"assistant", "content": str, "created_at": iso,
     # assistant messages only:
     "reasoning": str, "sources": [...], "refused": bool}

``pool`` is the conversation's *last-used* knowledge pool — display/resume
convenience only. Retrieval scoping is always driven by the pool sent with
each individual request (main.py), never read back from here.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CONV_PREFIX = "conversation:"
_INDEX_PREFIX = "conversation_index:"


def _key(user_id: str, conversation_id: str) -> str:
    return f"{_CONV_PREFIX}{user_id}:{conversation_id}"


def _index_key(user_id: str) -> str:
    return f"{_INDEX_PREFIX}{user_id}"


def create_conversation(redis_client, user_id: str, pool: str = "", title: str = "New chat") -> Dict[str, Any]:
    """Create an empty conversation and return it."""
    conversation_id = uuid.uuid4().hex
    now = datetime.now().isoformat()
    conv = {
        "id": conversation_id,
        "user_id": user_id,
        "pool": pool or "",
        "title": (title or "New chat").strip() or "New chat",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    redis_client.set(_key(user_id, conversation_id), json.dumps(conv))
    redis_client.zadd(_index_key(user_id), {conversation_id: time.time()})
    return conv


def get_conversation(redis_client, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
    raw = redis_client.get(_key(user_id, conversation_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        logger.error(f"Corrupt conversation blob {conversation_id} for user {user_id}")
        return None


def list_conversations(redis_client, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Summaries (no message bodies), newest-touched first."""
    ids = redis_client.zrevrange(_index_key(user_id), 0, limit - 1)
    out = []
    for conversation_id in ids:
        conv = get_conversation(redis_client, user_id, conversation_id)
        if conv is None:
            # Index entry survived a deleted/expired conversation — self-heal.
            redis_client.zrem(_index_key(user_id), conversation_id)
            continue
        last = conv["messages"][-1] if conv["messages"] else None
        out.append({
            "id": conv["id"],
            "title": conv["title"],
            "pool": conv["pool"],
            "message_count": len(conv["messages"]),
            "preview": (last["content"][:120] if last else ""),
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
        })
    return out


def append_message(
    redis_client, user_id: str, conversation_id: str, role: str, content: str,
    *, pool: Optional[str] = None, **extra: Any,
) -> Optional[Dict[str, Any]]:
    """
    Append one message and touch the conversation's ``updated_at`` + index
    score. When ``pool`` is given, also updates the conversation's stored
    last-used pool (called once per turn, on the assistant message).
    Returns the updated conversation, or ``None`` if it doesn't exist.
    """
    conv = get_conversation(redis_client, user_id, conversation_id)
    if conv is None:
        return None
    now = datetime.now().isoformat()
    message = {"role": role, "content": content, "created_at": now, **extra}
    conv["messages"].append(message)
    conv["updated_at"] = now
    if pool is not None:
        conv["pool"] = pool
    redis_client.set(_key(user_id, conversation_id), json.dumps(conv))
    redis_client.zadd(_index_key(user_id), {conversation_id: time.time()})
    return conv


def rename_conversation(redis_client, user_id: str, conversation_id: str, title: str) -> Optional[Dict[str, Any]]:
    conv = get_conversation(redis_client, user_id, conversation_id)
    if conv is None:
        return None
    conv["title"] = (title or "").strip() or "Untitled"
    redis_client.set(_key(user_id, conversation_id), json.dumps(conv))
    return conv


def delete_conversation(redis_client, user_id: str, conversation_id: str) -> bool:
    """Returns True if the conversation existed and was deleted."""
    existed = bool(redis_client.exists(_key(user_id, conversation_id)))
    redis_client.delete(_key(user_id, conversation_id))
    redis_client.zrem(_index_key(user_id), conversation_id)
    return existed


def enforce_conversation_limit(redis_client, user_id: str, limit: int) -> None:
    """
    Cap saved conversations per plan: if this user already has ``limit`` (or
    more), delete the least-recently-touched one(s) — via the sorted index,
    no KEYS/SCAN — so creating one more still respects the cap. Auto-evicts
    silently (no blocking/upgrade nag); called right before creating a new
    conversation. No-op if ``limit`` is falsy or <= 0 (unlimited).
    """
    if not limit or limit <= 0:
        return
    index_key = _index_key(user_id)
    count = redis_client.zcard(index_key)
    while count >= limit:
        oldest = redis_client.zrange(index_key, 0, 0)  # ascending score = least-recently-touched
        if not oldest:
            break
        delete_conversation(redis_client, user_id, oldest[0])
        count -= 1
