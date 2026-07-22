"""
Conversation management endpoints.

Creating a conversation is deliberately **not** exposed here — it happens
implicitly on the first ``POST /query`` or ``/query/stream`` call that omits
``conversation_id`` (see main.py), so the sidebar never accumulates empty
conversations from a "New chat" click that never sent a message.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import require_current_user
from auth.redis_client import redis_client
from chat import store as chat_store
from chat.schemas import ConversationDetail, ConversationSummary, RenameRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/conversations", tags=["Chat"], summary="List conversations", response_model=dict)
async def list_conversations(user_id: str = Depends(require_current_user)):
    summaries = chat_store.list_conversations(redis_client, user_id)
    return {"conversations": [ConversationSummary(**s) for s in summaries]}


@router.get("/conversations/{conversation_id}", tags=["Chat"], summary="Get a conversation", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, user_id: str = Depends(require_current_user)):
    conv = chat_store.get_conversation(redis_client, user_id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
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
    return {"status": "deleted"}
