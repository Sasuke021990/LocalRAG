"""Auth endpoints: signup, login, logout, me, Google OAuth, password reset."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse

from auth import email_service, google_oauth, passwords, store, tokens
from auth.dependencies import require_current_user
from auth.redis_client import redis_client
from auth.schemas import (
    ChangePasswordSchema,
    GoogleTokenExchangeSchema,
    LoginRequest,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    SignupRequest,
    UserOut,
)
from utils import system_settings
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


def _is_effective_admin(user: dict) -> bool:
    """Admin if the stored flag is set OR the email matches the env ADMIN_EMAIL."""
    flag = bool(user.get("is_admin"))
    env = bool(config.ADMIN_EMAIL) and user["email"].lower() == config.ADMIN_EMAIL.lower()
    return flag or env


def _user_out(user: dict, token: str) -> AuthResponse:
    return AuthResponse(
        user_id=user["user_id"],
        username=user.get("username", ""),
        email=user["email"],
        storage_used_bytes=user["storage_used_bytes"],
        storage_quota_bytes=user["storage_quota_bytes"],
        plan=user.get("plan", "free"),
        is_admin=_is_effective_admin(user),
        session_token=token,
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest, response: Response):
    if not system_settings.signups_enabled(redis_client):
        raise HTTPException(status_code=403, detail="Public signups are currently disabled")
    try:
        user_id = store.create_user(
            redis_client, body.email, password_hash=passwords.hash_password(body.password),
            username=body.username,
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


@router.post("/change-password")
async def change_password(
    body: ChangePasswordSchema,
    response: Response,
    user_id: str = Depends(require_current_user),
):
    """
    Change the signed-in user's password. Verifies the current password,
    then sets the new one and bumps token_version — which invalidates every
    *other* existing session. The current client is re-issued a fresh
    session cookie carrying the new token_version, so it stays logged in.
    """
    user = store.get_user_by_id(redis_client, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user["password_hash"] or not passwords.verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    store.set_password(redis_client, user_id, passwords.hash_password(body.new_password))
    store.bump_token_version(redis_client, user_id)
    new_version = user["token_version"] + 1
    _set_session_cookie(response, user_id, new_version)
    return {"status": "password_updated"}


@router.get("/me", response_model=UserOut)
async def me(user_id: str = Depends(require_current_user)):
    user = store.get_user_by_id(redis_client, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return UserOut(
        user_id=user["user_id"],
        username=user.get("username", ""),
        email=user["email"],
        storage_used_bytes=user["storage_used_bytes"],
        storage_quota_bytes=user["storage_quota_bytes"],
        plan=user.get("plan", "free"),
        is_admin=_is_effective_admin(user),
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


def _resolve_google_user(userinfo: dict) -> dict:
    """Find-or-link-or-create a user from Google userinfo. Returns the user dict."""
    user = store.get_user_by_google_sub(redis_client, userinfo["sub"])
    if user is None:
        user = store.get_user_by_email(redis_client, userinfo["email"])
        if user is not None:
            store.link_google_account(redis_client, user["user_id"], userinfo["sub"])
        else:
            user_id = store.create_user(
                redis_client, email=userinfo["email"], google_sub=userinfo["sub"],
                username=userinfo.get("name", ""),
            )
            user = store.get_user_by_id(redis_client, user_id)
    return user


@router.get("/google/callback")
async def google_callback(code: str):
    """Web flow: Google redirects here; we set a cookie and redirect to the app."""
    user = _resolve_google_user(google_oauth.exchange_code_for_userinfo(code))
    # Set the cookie on the RedirectResponse itself, not on an injected
    # Response param: when a handler *returns* a Response object, FastAPI
    # discards the injected response's headers (incl. Set-Cookie). Setting
    # it here is the only way the browser actually receives the session.
    redirect = RedirectResponse(f"{config.FRONTEND_BASE_URL}/")
    _set_session_cookie(redirect, user["user_id"], user["token_version"])
    return redirect


@router.post("/google/token-exchange", response_model=AuthResponse)
async def google_token_exchange(body: GoogleTokenExchangeSchema):
    """
    Native/mobile flow: the app completes Google's consent in a system browser,
    receives the authorization ``code`` via its ``vaultly://`` deep link, and
    POSTs it here. Returns the user + ``session_token`` as JSON (no cookie/
    redirect) — the app stores the token in the OS keychain. Reuses the exact
    same find-or-link-or-create logic as the web callback.
    """
    user = _resolve_google_user(google_oauth.exchange_code_for_userinfo(body.code))
    token = tokens.create_session_token(user["user_id"], user["token_version"])
    return _user_out(user, token)


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
