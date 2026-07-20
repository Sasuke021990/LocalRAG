"""Pydantic models for the admin API."""

from typing import Any

from pydantic import BaseModel, field_validator


class QuotaUpdate(BaseModel):
    quota_bytes: int

    @field_validator("quota_bytes")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("quota_bytes cannot be negative")
        return v


class StatusUpdate(BaseModel):
    is_active: bool


class AdminFlagUpdate(BaseModel):
    is_admin: bool


class SettingUpdate(BaseModel):
    name: str
    value: Any
