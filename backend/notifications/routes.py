"""
Push-notification device registration.

Guarded by ``require_session_user`` (a real browser/mobile session) rather
than ``require_current_user``, matching integrations/routes.py: an MCP/API
token can read and write the owner's documents, but must not be able to
attach a device that then receives that account's notifications.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import require_session_user
from auth.redis_client import redis_client
from notifications import store

logger = logging.getLogger(__name__)

router = APIRouter()


class DeviceTokenRequest(BaseModel):
    token: str


@router.post("/device", tags=["Notifications"], summary="Register this device for push notifications")
async def register_device(body: DeviceTokenRequest, user_id: str = Depends(require_session_user)):
    """
    Attach an Expo push token to the signed-in user, so background work
    (a finished upload, the daily insight) can notify them.

    Idempotent, and safe to call on every app launch — the client re-reads
    its token each time, and Expo can rotate it. Registering a token that
    currently belongs to a different account moves it: the same physical
    device must never keep receiving the previous user's notifications.
    """
    if not store.register_token(redis_client, user_id, body.token):
        raise HTTPException(status_code=400, detail="Invalid push token")
    return {"status": "registered"}


@router.delete("/device", tags=["Notifications"], summary="Unregister this device")
async def unregister_device(body: DeviceTokenRequest, user_id: str = Depends(require_session_user)):
    """
    Detach a device token from the signed-in user — called on logout so the
    next person to use this device doesn't receive their notifications.
    Always succeeds, including for an unknown token (nothing to detach is a
    valid outcome, not an error).
    """
    store.unregister_token(redis_client, user_id, body.token)
    return {"status": "unregistered"}
