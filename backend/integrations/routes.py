"""
Integrations management endpoints: per-user MCP/API tokens and webhooks.

Every route here is guarded by ``require_session_user`` (a real
browser/mobile session) — **not** ``require_current_user`` — so an
MCP/API token can read/write the owner's data but cannot mint new tokens
or register webhooks (privilege containment; see auth.dependencies).
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from auth.dependencies import require_session_user
from auth.redis_client import redis_client
from integrations import mcp_tokens, webhooks
from integrations.schemas import (
    TokenCreateRequest,
    TokenCreateResponse,
    TokenOut,
    WebhookCreateRequest,
    WebhookOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── MCP / API tokens ─────────────────────────────────────────────────────────

@router.post("/tokens", response_model=TokenCreateResponse, tags=["Integrations"])
async def create_token(body: TokenCreateRequest, user_id: str = Depends(require_session_user)):
    """
    Mint a new API token for the current user. The plaintext token is
    returned **once** in this response and cannot be recovered later —
    store it securely.
    """
    token, meta = mcp_tokens.create_token(redis_client, user_id, body.name)
    return TokenCreateResponse(
        token_id=meta["token_id"],
        name=meta["name"],
        token=token,
        prefix=meta["prefix"],
        created_at=meta["created_at"],
    )


@router.get("/tokens", tags=["Integrations"])
async def list_tokens(user_id: str = Depends(require_session_user)):
    """List the current user's API tokens (metadata only — never the secret)."""
    items = [TokenOut(**t) for t in mcp_tokens.list_tokens(redis_client, user_id)]
    return {"tokens": items, "total": len(items)}


@router.delete("/tokens/{token_id}", tags=["Integrations"])
async def revoke_token(token_id: str, user_id: str = Depends(require_session_user)):
    """Revoke (permanently delete) one of the current user's API tokens."""
    if not mcp_tokens.revoke_token(redis_client, user_id, token_id):
        raise HTTPException(status_code=404, detail="Token not found")
    return {"status": "revoked", "token_id": token_id}


# ─── Webhooks ─────────────────────────────────────────────────────────────────

@router.post("/webhooks", response_model=WebhookOut, tags=["Integrations"])
async def create_webhook(body: WebhookCreateRequest, user_id: str = Depends(require_session_user)):
    """
    Register a webhook. Supported events: ``document.ingested``,
    ``document.deleted``, ``document.ingest_failed``. A signing secret is
    generated if not supplied and returned here so you can verify the
    ``X-Vaultly-Signature`` header on delivered events.
    """
    try:
        wh = webhooks.create_webhook(redis_client, user_id, body.url, body.events, body.secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return WebhookOut(**wh)


@router.get("/webhooks", tags=["Integrations"])
async def list_webhooks(user_id: str = Depends(require_session_user)):
    """List the current user's registered webhooks."""
    items = [WebhookOut(**w) for w in webhooks.list_webhooks(redis_client, user_id)]
    return {"webhooks": items, "total": len(items)}


@router.delete("/webhooks/{webhook_id}", tags=["Integrations"])
async def delete_webhook(webhook_id: str, user_id: str = Depends(require_session_user)):
    """Delete one of the current user's webhooks."""
    if not webhooks.delete_webhook(redis_client, user_id, webhook_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deleted", "webhook_id": webhook_id}


@router.post("/webhooks/{webhook_id}/test", tags=["Integrations"])
async def test_webhook(
    webhook_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_session_user),
):
    """Send a ``ping`` test event to a webhook to verify connectivity."""
    if webhooks.get_webhook(redis_client, user_id, webhook_id) is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    background_tasks.add_task(webhooks.deliver_test_event, redis_client, user_id, webhook_id)
    return {"status": "test_queued", "webhook_id": webhook_id}
