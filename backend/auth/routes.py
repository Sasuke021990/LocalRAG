"""Auth endpoints: signup, login, logout, me."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from auth import passwords, store, tokens
from auth.dependencies import require_current_user
from auth.redis_client import redis_client
from auth.schemas import LoginRequest, SignupRequest, UserOut
from utils.config import config

logger = logging.getLogger(__name__)

router = APIRouter()


class AuthResponse(UserOut):
    """UserOut plus the raw session token, for clients (mobile) that can't rely on the cookie."""
    session_token: str


def _set_session_cookie(response: Response, user_id: str, token_version: int) -> str:
    token = tokens.create_session_token(user_id, token_version)
    response.set_cookie(
        tokens.SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=config.SESSION_COOKIE_MAX_AGE_SECONDS,
    )
    return token


def _user_out(user: dict, token: str) -> AuthResponse:
    return AuthResponse(
        user_id=user["user_id"],
        email=user["email"],
        storage_used_bytes=user["storage_used_bytes"],
        storage_quota_bytes=user["storage_quota_bytes"],
        session_token=token,
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest, response: Response):
    try:
        user_id = store.create_user(
            redis_client, body.email, password_hash=passwords.hash_password(body.password)
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Email already registered")

    token = _set_session_cookie(response, user_id, token_version=0)
    user = store.get_user_by_id(redis_client, user_id)
    logger.info(f"New signup: {user_id}")
    return _user_out(user, token)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, response: Response):
    user = store.get_user_by_email(redis_client, body.email)
    if not user or not user["password_hash"] or not passwords.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _set_session_cookie(response, user["user_id"], user["token_version"])
    return _user_out(user, token)


@router.post("/logout")
async def logout(response: Response):
    """No auth required — logging out when already logged out is a safe no-op."""
    response.delete_cookie(tokens.SESSION_COOKIE_NAME)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
async def me(user_id: str = Depends(require_current_user)):
    user = store.get_user_by_id(redis_client, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return UserOut(
        user_id=user["user_id"],
        email=user["email"],
        storage_used_bytes=user["storage_used_bytes"],
        storage_quota_bytes=user["storage_quota_bytes"],
    )
