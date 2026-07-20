"""
Per-user MCP / API tokens for Vaultly.

A token is a long-lived, individually-revocable credential a user mints
in the dashboard and pastes into an MCP client (Claude Desktop, etc.) or
any API caller. It authenticates as that user against the same
session-protected routes a browser session would reach (see
``auth.dependencies.require_current_user``).

Security model
--------------
- Tokens are opaque (``vlt_<43 url-safe chars>``), never JWTs — the
  ``vlt_`` prefix lets the auth dependency dispatch on them in O(1)
  without attempting a JWT decode, and opaque tokens can be revoked
  instantly (no version counter needed).
- Only the SHA-256 hash of a token is ever stored. The plaintext is
  returned exactly once, at creation time, and cannot be recovered
  afterwards — losing it means minting a new one.
- ``list_tokens`` returns display metadata only (a short recognizable
  prefix, name, timestamps) — never the hash or plaintext.

Key schema
----------
mcp_token_lookup:<sha256(token)>   STRING -> "<user_id>:<token_id>"   (O(1) auth resolution)
mcp_tokens:<user_id>               SET    -> {token_id, ...}          (listing)
mcp_token:<user_id>:<token_id>     HASH   -> {name, prefix, hash, created_at, last_used_at}
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "vlt_"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _lookup_key(token_hash: str) -> str:
    return f"mcp_token_lookup:{token_hash}"


def _set_key(user_id: str) -> str:
    return f"mcp_tokens:{user_id}"


def _meta_key(user_id: str, token_id: str) -> str:
    return f"mcp_token:{user_id}:{token_id}"


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def create_token(redis_client, user_id: str, name: str) -> Tuple[str, Dict[str, Any]]:
    """
    Mint a new token for ``user_id``.

    Returns ``(token_plaintext, meta)``. The plaintext is shown to the
    caller exactly once; only its hash is persisted.
    """
    token = generate_token()
    token_id = uuid.uuid4().hex
    token_hash = _hash(token)
    created_at = datetime.now().isoformat()
    prefix = token[:12]

    redis_client.set(_lookup_key(token_hash), f"{user_id}:{token_id}")
    redis_client.sadd(_set_key(user_id), token_id)
    redis_client.hset(
        _meta_key(user_id, token_id),
        mapping={
            "name": name,
            "prefix": prefix,
            "hash": token_hash,
            "created_at": created_at,
            "last_used_at": "",
        },
    )

    logger.info(f"Created MCP token {token_id} for user {user_id}")
    meta = {
        "token_id": token_id,
        "name": name,
        "prefix": prefix,
        "created_at": created_at,
        "last_used_at": "",
    }
    return token, meta


def _public_meta(raw: Dict[str, Any], token_id: str) -> Dict[str, Any]:
    """Strip the server-only ``hash`` field before returning to a caller."""
    return {
        "token_id": token_id,
        "name": raw.get("name", ""),
        "prefix": raw.get("prefix", ""),
        "created_at": raw.get("created_at", ""),
        "last_used_at": raw.get("last_used_at", ""),
    }


def list_tokens(redis_client, user_id: str) -> List[Dict[str, Any]]:
    token_ids = redis_client.smembers(_set_key(user_id))
    tokens = []
    for token_id in token_ids:
        raw = redis_client.hgetall(_meta_key(user_id, token_id))
        if raw:
            tokens.append(_public_meta(raw, token_id))
    tokens.sort(key=lambda t: t["created_at"])
    return tokens


def revoke_token(redis_client, user_id: str, token_id: str) -> bool:
    """Delete a token by id. Returns False if it doesn't exist for this user."""
    meta_key = _meta_key(user_id, token_id)
    raw = redis_client.hgetall(meta_key)
    if not raw:
        return False

    token_hash = raw.get("hash")
    if token_hash:
        redis_client.delete(_lookup_key(token_hash))
    redis_client.delete(meta_key)
    redis_client.srem(_set_key(user_id), token_id)
    logger.info(f"Revoked MCP token {token_id} for user {user_id}")
    return True


def resolve_token(redis_client, token: str) -> Optional[str]:
    """
    Resolve a presented token to its owning ``user_id``, or ``None`` if it
    isn't a valid Vaultly token. Best-effort updates ``last_used_at``.
    """
    if not token or not token.startswith(TOKEN_PREFIX):
        return None

    mapping = redis_client.get(_lookup_key(_hash(token)))
    if not mapping:
        return None

    user_id, _, token_id = mapping.partition(":")
    if not user_id or not token_id:
        return None

    try:
        redis_client.hset(_meta_key(user_id, token_id), "last_used_at", datetime.now().isoformat())
    except Exception:  # last-used tracking is non-critical
        pass

    return user_id
