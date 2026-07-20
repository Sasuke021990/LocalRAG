"""FastAPI dependencies for resolving the current authenticated user.

Two dependencies are exposed:

- ``require_current_user`` — accepts either a browser/mobile **session**
  (JWT in the ``Authorization: Bearer`` header or the session cookie) **or**
  a long-lived **MCP/API token** (``vlt_…``). Used on every data route so
  external API/MCP clients and browsers reach the same endpoints.
- ``require_session_user`` — accepts a session **only**, never an MCP
  token. Used on the ``/integrations/*`` management routes so a leaked
  token can read/write the owner's data but cannot mint new tokens or
  register webhooks (privilege containment).
"""

import jwt
from fastapi import HTTPException, Request

from auth import store, tokens
from auth.redis_client import redis_client
from integrations import mcp_tokens


def _extract_token(request: Request) -> str:
    """Pull the credential from the Authorization header (preferred) or cookie."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:]
    return request.cookies.get(tokens.SESSION_COOKIE_NAME) or ""


def _user_from_session(token: str) -> str:
    """Validate a session JWT and return its user_id, or raise 401/403."""
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


async def require_current_user(request: Request) -> str:
    """
    Resolve the authenticated user's ID from a session (JWT bearer/cookie)
    or an MCP/API token (``vlt_…`` bearer).

    Raises 401 if there's no credential or it's invalid/expired/revoked,
    403 if the account has been disabled.
    """
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # MCP/API token path — opaque, prefix-dispatched (no JWT decode).
    if token.startswith(mcp_tokens.TOKEN_PREFIX):
        user_id = mcp_tokens.resolve_token(redis_client, token)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid API token")
        user = store.get_user_by_id(redis_client, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        if not user["is_active"]:
            raise HTTPException(status_code=403, detail="Account disabled")
        return user_id

    return _user_from_session(token)


async def require_session_user(request: Request) -> str:
    """
    Like ``require_current_user`` but rejects MCP/API tokens — only a real
    browser/mobile session is accepted. Guards the integrations management
    routes so a token cannot be used to mint more tokens or register
    webhooks.
    """
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if token.startswith(mcp_tokens.TOKEN_PREFIX):
        raise HTTPException(
            status_code=401,
            detail="A logged-in session is required for this action (API tokens are not accepted)",
        )
    return _user_from_session(token)
