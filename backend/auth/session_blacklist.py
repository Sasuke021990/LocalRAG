"""
Server-side revocation for individual session JWTs.

Session tokens are stateless (see tokens.py) and normally stay valid until
their ``exp`` claim even after the user logs out — a captured bearer token
would keep working. ``bump_token_version`` (used by password change/reset)
already handles the "kill every session" case, but that's too broad for a
plain logout, which should only kill *this* device's token.

This module lets ``POST /auth/logout`` revoke the specific token being used,
via its ``jti`` claim, without touching any other session. Blacklist entries
self-expire at the token's original ``exp`` via Redis TTL, so the set never
grows unbounded.

Key schema
----------
session_blacklist:<jti>   STRING "1"   (TTL = seconds remaining until exp)
"""

import time


def _key(jti: str) -> str:
    return f"session_blacklist:{jti}"


def blacklist(redis_client, jti: str, exp: float) -> None:
    """Revoke the token identified by ``jti``. ``exp`` is its Unix expiry
    (the JWT's ``exp`` claim) -- the blacklist entry lives no longer than the
    token would have anyway. No-op if ``jti`` is falsy (e.g. a pre-existing
    token minted before this claim was added)."""
    if not jti:
        return
    ttl = int(exp - time.time())
    if ttl <= 0:
        return  # already expired -- nothing to blacklist
    redis_client.setex(_key(jti), ttl, "1")


def is_blacklisted(redis_client, jti: str) -> bool:
    if not jti:
        return False
    return bool(redis_client.exists(_key(jti)))
