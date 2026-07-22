"""Pydantic request/response models for conversation endpoints."""

from typing import Any, Dict, List

from pydantic import BaseModel


class ConversationSummary(BaseModel):
    id: str
    title: str
    pool: str
    message_count: int
    preview: str
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str
    reasoning: str = ""
    sources: List[Dict[str, Any]] = []
    refused: bool = False


class ConversationDetail(BaseModel):
    id: str
    title: str
    pool: str
    created_at: str
    updated_at: str
    messages: List[MessageOut]


class RenameRequest(BaseModel):
    title: str
