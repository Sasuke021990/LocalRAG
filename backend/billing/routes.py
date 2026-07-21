"""
Billing API — a **stub** for Stripe. Upgrading/downgrading changes the user's
plan and quota immediately, with no payment. The only thing a real Stripe
integration would add here is a "payment succeeded" gate before ``set_plan``.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import require_current_user
from auth.redis_client import redis_client
from billing import plans
from billing import store as billing_store

logger = logging.getLogger(__name__)

router = APIRouter()


class CheckoutRequest(BaseModel):
    plan: str


@router.get("/plans", tags=["Billing"], summary="List available plans")
async def list_plans(_user_id: str = Depends(require_current_user)):
    return {"plans": list(plans.PLANS.values())}


@router.get("/subscription", tags=["Billing"], summary="Current plan")
async def subscription(user_id: str = Depends(require_current_user)):
    plan = billing_store.get_plan(redis_client, user_id)
    return {"plan": plan, "quota_bytes": plans.quota_for(plan)}


@router.post("/checkout", tags=["Billing"], summary="Upgrade/switch plan (stub — no payment)")
async def checkout(body: CheckoutRequest, user_id: str = Depends(require_current_user)):
    if not plans.is_valid_plan(body.plan):
        raise HTTPException(status_code=400, detail=f"Unknown plan '{body.plan}'")
    billing_store.set_plan(redis_client, user_id, body.plan)
    return {
        "status": "activated",
        "stub": True,  # honest: no real charge happened
        "plan": body.plan,
        "quota_bytes": plans.quota_for(body.plan),
    }


@router.post("/cancel", tags=["Billing"], summary="Downgrade to Free")
async def cancel(user_id: str = Depends(require_current_user)):
    billing_store.set_plan(redis_client, user_id, plans.DEFAULT_PLAN)
    return {"status": "cancelled", "plan": plans.DEFAULT_PLAN, "quota_bytes": plans.quota_for(plans.DEFAULT_PLAN)}
