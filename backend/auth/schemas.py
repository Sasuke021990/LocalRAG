"""Pydantic request/response models for auth endpoints."""

from pydantic import BaseModel, EmailStr, field_validator


def _validate_password_length(v: str) -> str:
    if len(v) < 8:
        raise ValueError("password must be at least 8 characters")
    return v


class SignupRequest(BaseModel):
    email: EmailStr
    password: str

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
    email: str
    storage_used_bytes: int
    storage_quota_bytes: int
    is_admin: bool = False
