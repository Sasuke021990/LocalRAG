"""
Admin data-access layer — METADATA ONLY.

BINDING PRIVACY RULE (task_plan.md §3): no function in this module may
read or return another user's document content, chunk text, query/chat
history, or semantic-cache values. Admins see account metadata (email,
storage used/quota, status, created_at) and *counts* only. Counts are
computed with ``len(keys(pattern))`` / ``SCARD`` — the values behind those
keys are never read here. Any future addition to this module must uphold
that rule; it is enforced by ``tests/test_admin_store.py``'s
no-content-leak test.

Key namespaces owned by a user (used for counts + cascade delete):
    user:<uid>                     account record
    user_email_index:<email>       email -> uid
    user_username_index:<username> username -> uid
    user_google_index:<sub>        google sub -> uid
    document:<uid>:*               document blobs
    chunk:<uid>:*                  RediSearch chunk hashes
    semantic_cache:<uid>:*         per-user query cache
    mcp_token:<uid>:*              token metadata hashes
    mcp_tokens:<uid>               token id set
    mcp_token_lookup:<hash>        token hash -> uid  (resolved via token meta)
    webhook:<uid>:*                webhook hashes
    webhooks:<uid>                 webhook id set
    conversation:<uid>:*           conversation blobs (chat history)
    conversation_index:<uid>       conversation recency zset
"""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_PREFIX = "semantic_cache:"  # matches SemanticCache's production default


def _cast_user(raw: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "username": raw.get("username", ""),
        "email": raw.get("email", ""),
        "created_at": raw.get("created_at", ""),
        "storage_used_bytes": int(raw.get("storage_used_bytes", 0)),
        "storage_quota_bytes": int(raw.get("storage_quota_bytes", 0)),
        "is_admin": bool(int(raw.get("is_admin", 0))),
        "is_active": bool(int(raw.get("is_active", 1))),
    }


def count_documents(redis_client, user_id: str) -> int:
    return len(redis_client.keys(f"document:{user_id}:*"))


def count_webhooks(redis_client, user_id: str) -> int:
    return redis_client.scard(f"webhooks:{user_id}")


def count_tokens(redis_client, user_id: str) -> int:
    return redis_client.scard(f"mcp_tokens:{user_id}")


def _user_summary(redis_client, user_id: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    meta = _cast_user(raw, user_id)
    meta["document_count"] = count_documents(redis_client, user_id)
    return meta


def list_users(redis_client, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    users = []
    for key in redis_client.keys("user:*"):
        user_id = key.split(":", 1)[1]
        raw = redis_client.hgetall(key)
        if raw:
            users.append(_user_summary(redis_client, user_id, raw))
    users.sort(key=lambda u: u["created_at"])
    return users[offset : offset + limit]


def get_user_detail(redis_client, user_id: str) -> Optional[Dict[str, Any]]:
    raw = redis_client.hgetall(f"user:{user_id}")
    if not raw:
        return None
    detail = _user_summary(redis_client, user_id, raw)
    detail["webhook_count"] = count_webhooks(redis_client, user_id)
    detail["token_count"] = count_tokens(redis_client, user_id)
    return detail


def set_user_quota(redis_client, user_id: str, quota_bytes: int) -> Optional[Dict[str, Any]]:
    if not redis_client.exists(f"user:{user_id}"):
        return None
    redis_client.hset(f"user:{user_id}", "storage_quota_bytes", int(quota_bytes))
    return get_user_detail(redis_client, user_id)


def set_user_active(redis_client, user_id: str, active: bool) -> Optional[Dict[str, Any]]:
    if not redis_client.exists(f"user:{user_id}"):
        return None
    redis_client.hset(f"user:{user_id}", "is_active", 1 if active else 0)
    return get_user_detail(redis_client, user_id)


def set_user_admin(redis_client, user_id: str, is_admin: bool) -> Optional[Dict[str, Any]]:
    if not redis_client.exists(f"user:{user_id}"):
        return None
    redis_client.hset(f"user:{user_id}", "is_admin", 1 if is_admin else 0)
    return get_user_detail(redis_client, user_id)


def system_stats(redis_client) -> Dict[str, Any]:
    total_users = 0
    active_users = 0
    admin_users = 0
    total_storage_used = 0
    for key in redis_client.keys("user:*"):
        raw = redis_client.hgetall(key)
        if not raw:
            continue
        total_users += 1
        if int(raw.get("is_active", 1)):
            active_users += 1
        if int(raw.get("is_admin", 0)):
            admin_users += 1
        total_storage_used += int(raw.get("storage_used_bytes", 0))

    return {
        "total_users": total_users,
        "active_users": active_users,
        "admin_users": admin_users,
        "total_storage_used_bytes": total_storage_used,
        "total_documents": len(redis_client.keys("document:*")),
        "total_webhooks": len(redis_client.keys("webhook:*")),
        "total_tokens": len(redis_client.keys("mcp_token:*")),
    }


def delete_user_completely(redis_client, user_id: str, data_dir: str = "/app/data") -> bool:
    """
    Hard-delete a user and every namespace they own (Redis keys + disk
    backups). Metadata-only: keys are removed by pattern, never read for
    content beyond the indices needed to clean up (email/google sub for
    the reverse indices, token hashes for the lookup keys).

    Returns False if the user doesn't exist.
    """
    user_key = f"user:{user_id}"
    raw = redis_client.hgetall(user_key)
    if not raw:
        return False

    # Reverse indices (need the values stored on the user record).
    email = raw.get("email", "")
    username = raw.get("username", "")
    google_sub = raw.get("google_sub", "")
    if email:
        redis_client.delete(f"user_email_index:{email.lower()}")
    if username:
        redis_client.delete(f"user_username_index:{username.lower()}")
    if google_sub:
        redis_client.delete(f"user_google_index:{google_sub}")

    # Token lookup keys (hash stored on each token meta hash).
    for token_id in redis_client.smembers(f"mcp_tokens:{user_id}"):
        token_hash = redis_client.hget(f"mcp_token:{user_id}:{token_id}", "hash")
        if token_hash:
            redis_client.delete(f"mcp_token_lookup:{token_hash}")

    # Everything keyed under the user, by pattern.
    patterns = [
        f"document:{user_id}:*",
        f"chunk:{user_id}:*",
        f"{CACHE_PREFIX}{user_id}:*",
        f"mcp_token:{user_id}:*",
        f"mcp_tokens:{user_id}",
        f"webhook:{user_id}:*",
        f"webhooks:{user_id}",
        f"conversation:{user_id}:*",
        f"conversation_index:{user_id}",
    ]
    for pattern in patterns:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)

    redis_client.delete(user_key)

    # Disk backups.
    user_dir = Path(data_dir) / user_id
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)

    logger.info(f"Admin hard-deleted user {user_id} ({email}) and all owned data")
    return True
