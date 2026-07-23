"""
Conversation management endpoints.

Creating a conversation is deliberately **not** exposed here — it happens
implicitly on the first ``POST /query`` or ``/query/stream`` call that omits
``conversation_id`` (see main.py), so the sidebar never accumulates empty
conversations from a "New chat" click that never sent a message.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import require_current_user
from auth.redis_client import redis_client
from chat import store as chat_store
from chat.schemas import ConversationDetail, ConversationSummary, RenameRequest
from retrieval import semantic_cache, vector_index

logger = logging.getLogger(__name__)

router = APIRouter()


def _hydrate_sources(redis_client_, user_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Persisted sources are trimmed to just file_name/pool/chunk_index/score
    (see main.py's _slim_sources — ~70% smaller than including the full
    passage text). Re-attach the text here from the still-durable chunk
    HASHes, at read time — a display-only concern, paid only when a saved
    conversation is opened, never on the hot chat-send path. Falls back to
    an empty string if the source chunk was since deleted/moved (graceful
    degradation, not an error).
    """
    for msg in messages:
        for source in msg.get("sources") or []:
            if source.get("content"):
                continue  # already has it (e.g. data saved before this change)
            key = vector_index.chunk_key(
                user_id, source.get("pool", ""), source.get("file_name", ""), source.get("chunk_index", 0),
            )
            source["content"] = redis_client_.hget(key, "content") or ""
    return messages


@router.get("/conversations", tags=["Chat"], summary="List conversations", response_model=dict)
async def list_conversations(user_id: str = Depends(require_current_user)):
    summaries = chat_store.list_conversations(redis_client, user_id)
    return {"conversations": [ConversationSummary(**s) for s in summaries]}


@router.get("/conversations/{conversation_id}", tags=["Chat"], summary="Get a conversation", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, user_id: str = Depends(require_current_user)):
    conv = chat_store.get_conversation(redis_client, user_id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv["messages"] = _hydrate_sources(redis_client, user_id, conv["messages"])
    return conv


@router.patch("/conversations/{conversation_id}", tags=["Chat"], summary="Rename a conversation")
async def rename_conversation(conversation_id: str, body: RenameRequest, user_id: str = Depends(require_current_user)):
    conv = chat_store.rename_conversation(redis_client, user_id, conversation_id, body.title)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "renamed", "title": conv["title"]}


@router.delete("/conversations/{conversation_id}", tags=["Chat"], summary="Delete a conversation")
async def delete_conversation(conversation_id: str, user_id: str = Depends(require_current_user)):
    if not chat_store.delete_conversation(redis_client, user_id, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    # Clear this user's cached answers so re-asking a question after deleting a
    # conversation genuinely re-runs the LLM (a fresh start) instead of getting
    # an instant cached reply that makes the old chat feel like it's still there.
    semantic_cache.clear_user_cache(redis_client, user_id)
    return {"status": "deleted"}
