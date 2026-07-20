"""FastAPI dependency for resolving the current authenticated user."""

import jwt
from fastapi import HTTPException, Request

from auth import store, tokens
from auth.redis_client import redis_client


async def require_current_user(request: Request) -> str:
    """
    Resolves the authenticated user's ID from either a Bearer token
    (mobile) or the session cookie (web) — the header is checked first
    since it's unambiguous when present; the cookie is the fallback for
    browser clients that never send an Authorization header.

    Raises 401 if there's no credential, it's invalid/expired, the user
    no longer exists, or the token's version doesn't match the user's
    current token_version (i.e. it was revoked by a password change or
    reset). Raises 403 if the account has been disabled.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
    else:
        token = request.cookies.get(tokens.SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = tokens.decode_session_token(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = store.get_user_by_id(redis_client, payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if payload.get("tv") != user["token_version"]:
        raise HTTPException(status_code=401, detail="Session revoked")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account disabled")

    return user["user_id"]
