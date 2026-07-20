"""Auth endpoints: signup, login, logout, me, Google OAuth, password reset."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse

from auth import email_service, google_oauth, passwords, store, tokens
from auth.dependencies import require_current_user
from auth.redis_client import redis_client
from auth.schemas import (
    LoginRequest,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    SignupRequest,
    UserOut,
)
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


# ─── Google OAuth ───────────────────────────────────────────────────────────

@router.get("/google/login")
async def google_login():
    """
    Redirects to Google's consent screen.

    NOTE: the CSRF ``state`` parameter is generated but not stored/verified
    on callback -- acceptable for a first pass on a self-hosted app, not
    for public exposure. See .plan/task_plan.md Open Questions #1.
    """
    state = uuid.uuid4().hex
    return RedirectResponse(google_oauth.build_authorization_url(state))


@router.get("/google/callback")
async def google_callback(code: str, response: Response):
    userinfo = google_oauth.exchange_code_for_userinfo(code)

    user = store.get_user_by_google_sub(redis_client, userinfo["sub"])
    if user is None:
        user = store.get_user_by_email(redis_client, userinfo["email"])
        if user is not None:
            store.link_google_account(redis_client, user["user_id"], userinfo["sub"])
        else:
            user_id = store.create_user(redis_client, email=userinfo["email"], google_sub=userinfo["sub"])
            user = store.get_user_by_id(redis_client, user_id)

    _set_session_cookie(response, user["user_id"], user["token_version"])
    return RedirectResponse(f"{config.FRONTEND_BASE_URL}/")


# ─── Password reset ─────────────────────────────────────────────────────────

@router.post("/password-reset/request")
async def password_reset_request(body: PasswordResetRequestSchema, background_tasks: BackgroundTasks):
    """
    Always returns 200 regardless of whether the email is registered --
    never leak account existence through response differences.
    """
    user = store.get_user_by_email(redis_client, body.email)
    if user is not None:
        token = store.create_password_reset_token(redis_client, user["user_id"])
        reset_link = f"{config.FRONTEND_BASE_URL}/reset-password.html?token={token}"
        background_tasks.add_task(email_service.send_password_reset_email, user["email"], reset_link)
    return {"status": "ok"}


@router.post("/password-reset/confirm")
async def password_reset_confirm(body: PasswordResetConfirmSchema):
    user_id = store.consume_password_reset_token(redis_client, body.token)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    store.set_password(redis_client, user_id, passwords.hash_password(body.new_password))
    # Bump token_version to invalidate any existing sessions -- including
    # one that might have been hijacked, which is exactly the scenario a
    # password reset is meant to recover from.
    store.bump_token_version(redis_client, user_id)
    return {"status": "password_updated"}
