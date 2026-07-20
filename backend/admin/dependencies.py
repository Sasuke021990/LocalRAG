"""
Admin authorization dependency.

An admin is a user whose stored ``is_admin`` flag is set **or** whose
email matches ``config.ADMIN_EMAIL`` (the operator/root admin). Admin
routes are **session-only** — an MCP/API token is never accepted, so a
leaked token can never reach the admin panel even if its owner is an
admin.

The env-level admin is *self-healing*: the first time they hit an admin
route, if their ``is_admin`` flag is still 0 it's flipped to 1 so the DB
stays consistent (they then appear as admin in listings/stats).
"""

from fastapi import HTTPException, Request

from auth import store
from auth.dependencies import _extract_token, _user_from_session
from auth.redis_client import redis_client
from integrations import mcp_tokens
from utils.config import config


async def require_admin_user(request: Request) -> str:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if token.startswith(mcp_tokens.TOKEN_PREFIX):
        raise HTTPException(
            status_code=401,
            detail="A logged-in session is required for admin actions (API tokens are not accepted)",
        )

    user_id = _user_from_session(token)
    user = store.get_user_by_id(redis_client, user_id)

    is_env_admin = bool(config.ADMIN_EMAIL) and user["email"].lower() == config.ADMIN_EMAIL.lower()
    if not (user["is_admin"] == 1 or is_env_admin):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Self-heal: persist the env-admin's flag so listings/stats reflect it.
    if is_env_admin and user["is_admin"] != 1:
        redis_client.hset(f"user:{user_id}", "is_admin", 1)

    return user_id
