"""Pydantic request/response models for auth endpoints."""

from pydantic import BaseModel, EmailStr, field_validator

from utils.config import config


def _validate_password_length(v: str) -> str:
    if len(v) < 8:
        raise ValueError("password must be at least 8 characters")
    return v


def _validate_username(v: str) -> str:
    # Optional at the API level (falls back to the email's local part server-
    # side, same as auth.store.create_user) — the signup *form* requires it,
    # but the API itself stays backward-compatible for other callers.
    v = (v or "").strip()
    if len(v) > 60:
        raise ValueError("username must be 60 characters or fewer")
    return v


class SignupRequest(BaseModel):
    username: str = ""
    email: EmailStr
    password: str

    _check_username = field_validator("username")(_validate_username)
    _check_password = field_validator("password")(_validate_password_length)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    token: str
    new_password: str

    _check_password = field_validator("new_password")(_validate_password_length)


class GoogleTokenExchangeSchema(BaseModel):
    code: str


class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str

    _check_password = field_validator("new_password")(_validate_password_length)


class UserOut(BaseModel):
    user_id: str
    username: str = ""
    email: str
    storage_used_bytes: int
    storage_quota_bytes: int
    plan: str = "free"
    is_admin: bool = False
    # Not passed explicitly by any route — Pydantic fills it from this
    # class-level default, sourced from Config (env), on every response that
    # doesn't set it. Read by the frontend's idle-session timer.
    idle_timeout_seconds: int = config.SESSION_IDLE_TIMEOUT_SECONDS
