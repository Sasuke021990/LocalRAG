"""
Per-user Expo push-notification device tokens.

A user can be signed in on several devices, so tokens are held in a SET per
user. The reverse index (token -> user) exists so a token can be reassigned
atomically: phones get handed over and accounts get switched, and a token
left attached to a previous user would deliver *their* notifications to
whoever is signed in now. Registration therefore always detaches the token
from any other user first.

Key schema (mirrors the webhooks SET+per-item convention)
---------------------------------------------------------
push_tokens:<user_id>      SET    -> {ExponentPushToken[...], ...}
push_token_owner:<token>   STRING -> user_id

Tokens are opaque routing addresses issued by Expo, not credentials — they
identify a device install, and Expo rejects sends to tokens that no longer
exist. They still deserve care: one is enough to send a user arbitrary
notification text, so they're never returned by any read API.
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

_TOKENS_PREFIX = "push_tokens:"
_OWNER_PREFIX = "push_token_owner:"

# Expo's token format. Validated on the way in so malformed values (or junk
# from a spoofed client) never reach the send path or accumulate in Redis.
# ExpoPushToken[...] is the modern spelling; ExponentPushToken[...] is the
# long-standing one still issued today — both are accepted by Expo's API.
_TOKEN_RE = re.compile(r"^Expo(nent)?PushToken\[[A-Za-z0-9._\-]+\]$")


def is_valid_token(token: str) -> bool:
    return bool(_TOKEN_RE.match((token or "").strip()))


def _tokens_key(user_id: str) -> str:
    return f"{_TOKENS_PREFIX}{user_id}"


def _owner_key(token: str) -> str:
    return f"{_OWNER_PREFIX}{token}"


def register_token(redis_client, user_id: str, token: str) -> bool:
    """
    Attach ``token`` to ``user_id``, detaching it from whichever user held it
    before (see module docstring — this is the "shared device" case, and
    skipping it would leak notifications across accounts).

    Returns False for a malformed token, True otherwise. Idempotent.
    """
    token = (token or "").strip()
    if not is_valid_token(token):
        logger.warning(f"Rejected malformed push token for user {user_id}")
        return False

    previous_owner = redis_client.get(_owner_key(token))
    if previous_owner and previous_owner != user_id:
        redis_client.srem(_tokens_key(previous_owner), token)
        logger.info(f"Push token reassigned from user {previous_owner} to {user_id}")

    redis_client.sadd(_tokens_key(user_id), token)
    redis_client.set(_owner_key(token), user_id)
    return True


def unregister_token(redis_client, user_id: str, token: str) -> None:
    """
    Detach one token from this user (called on logout). Only clears the
    owner index if this user actually still owns it — otherwise a stale
    logout could unhook a token that has since been claimed by someone else
    on the same device.
    """
    token = (token or "").strip()
    if not token:
        return
    redis_client.srem(_tokens_key(user_id), token)
    if redis_client.get(_owner_key(token)) == user_id:
        redis_client.delete(_owner_key(token))


def get_tokens(redis_client, user_id: str) -> List[str]:
    """Every device token currently registered to this user."""
    try:
        return sorted(redis_client.smembers(_tokens_key(user_id)))
    except Exception as exc:
        logger.warning(f"Could not read push tokens for user {user_id}: {exc}")
        return []


def remove_token_globally(redis_client, token: str) -> None:
    """
    Drop a token wherever it lives — used when Expo reports it as
    ``DeviceNotRegistered`` (app uninstalled, or the token was rotated), so
    dead tokens don't accumulate and get retried forever.
    """
    owner: Optional[str] = redis_client.get(_owner_key(token))
    if owner:
        redis_client.srem(_tokens_key(owner), token)
    redis_client.delete(_owner_key(token))


def clear_user(redis_client, user_id: str) -> None:
    """Remove every token for a user — called on account deletion."""
    for token in get_tokens(redis_client, user_id):
        redis_client.delete(_owner_key(token))
    redis_client.delete(_tokens_key(user_id))
