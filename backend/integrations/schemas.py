"""Pydantic request/response models for the integrations API (tokens + webhooks)."""

from typing import List, Optional

from pydantic import BaseModel, field_validator


def _validate_name(v: str) -> str:
    v = v.strip()
    if not (1 <= len(v) <= 64):
        raise ValueError("name must be between 1 and 64 characters")
    return v


# ─── MCP / API tokens ─────────────────────────────────────────────────────────

class TokenCreateRequest(BaseModel):
    name: str

    _check_name = field_validator("name")(_validate_name)


class TokenCreateResponse(BaseModel):
    token_id: str
    name: str
    token: str          # plaintext — returned exactly once, at creation
    prefix: str
    created_at: str


class TokenOut(BaseModel):
    token_id: str
    name: str
    prefix: str
    created_at: str
    last_used_at: str


# ─── Webhooks ─────────────────────────────────────────────────────────────────

class WebhookCreateRequest(BaseModel):
    url: str
    events: List[str]
    secret: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v

    @field_validator("events")
    @classmethod
    def _validate_events_nonempty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("at least one event must be specified")
        return v


class WebhookOut(BaseModel):
    webhook_id: str
    url: str
    events: List[str]
    secret: str
    is_active: bool
    created_at: str
    last_status: str
    last_delivered_at: str
    failure_count: int
