"""
Admin API — metadata-only user administration + runtime settings.

All routes require ``require_admin_user`` (session-only admin). Every data
read goes through ``admin.store``, which never returns document content
(see its module docstring). Self-protection guards prevent an admin from
locking out or deleting the root admin or themselves.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from admin import store as admin_store
from admin.dependencies import require_admin_user
from admin.schemas import AdminFlagUpdate, QuotaUpdate, SettingUpdate, StatusUpdate
from auth import store as auth_store
from auth.redis_client import redis_client
from utils import system_settings
from utils.config import config

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_env_admin(user_id: str) -> bool:
    if not config.ADMIN_EMAIL:
        return False
    user = auth_store.get_user_by_id(redis_client, user_id)
    return bool(user) and user["email"].lower() == config.ADMIN_EMAIL.lower()


# ─── Users ────────────────────────────────────────────────────────────────────

@router.get("/users", tags=["Admin"])
async def list_users(limit: int = 100, offset: int = 0, _admin: str = Depends(require_admin_user)):
    users = admin_store.list_users(redis_client, limit=limit, offset=offset)
    return {"users": users, "total": len(users)}


@router.get("/users/{user_id}", tags=["Admin"])
async def get_user(user_id: str, _admin: str = Depends(require_admin_user)):
    detail = admin_store.get_user_detail(redis_client, user_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="User not found")
    return detail


@router.patch("/users/{user_id}/quota", tags=["Admin"])
async def update_quota(user_id: str, body: QuotaUpdate, _admin: str = Depends(require_admin_user)):
    updated = admin_store.set_user_quota(redis_client, user_id, body.quota_bytes)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.patch("/users/{user_id}/status", tags=["Admin"])
async def update_status(user_id: str, body: StatusUpdate, _admin: str = Depends(require_admin_user)):
    if not body.is_active and _is_env_admin(user_id):
        raise HTTPException(status_code=400, detail="Cannot deactivate the root admin account")
    updated = admin_store.set_user_active(redis_client, user_id, body.is_active)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.patch("/users/{user_id}/admin", tags=["Admin"])
async def update_admin_flag(user_id: str, body: AdminFlagUpdate, _admin: str = Depends(require_admin_user)):
    if not body.is_admin and _is_env_admin(user_id):
        raise HTTPException(status_code=400, detail="Cannot revoke admin from the root admin account")
    updated = admin_store.set_user_admin(redis_client, user_id, body.is_admin)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.delete("/users/{user_id}", tags=["Admin"])
async def delete_user(user_id: str, admin_id: str = Depends(require_admin_user)):
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if _is_env_admin(user_id):
        raise HTTPException(status_code=400, detail="Cannot delete the root admin account")
    if not admin_store.delete_user_completely(redis_client, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted", "user_id": user_id}


# ─── System ───────────────────────────────────────────────────────────────────

@router.get("/stats", tags=["Admin"])
async def stats(_admin: str = Depends(require_admin_user)):
    return admin_store.system_stats(redis_client)


@router.get("/settings", tags=["Admin"])
async def get_settings(_admin: str = Depends(require_admin_user)):
    return {"settings": system_settings.get_all(redis_client)}


@router.patch("/settings", tags=["Admin"])
async def update_setting(body: SettingUpdate, _admin: str = Depends(require_admin_user)):
    try:
        value = system_settings.set_setting(redis_client, body.name, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"name": body.name, "value": value}
