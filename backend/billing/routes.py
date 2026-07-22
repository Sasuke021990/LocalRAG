"""
Billing API — a **stub** for Stripe. Upgrading/downgrading changes the user's
plan and quota immediately, with no payment. The only thing a real Stripe
integration would add here is a "payment succeeded" gate before ``set_plan``.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from auth import email_service
from auth.dependencies import require_current_user
from auth.redis_client import redis_client
from billing import plans
from billing import store as billing_store
from utils.config import config

logger = logging.getLogger(__name__)

router = APIRouter()


class CheckoutRequest(BaseModel):
    plan: str


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    company: str = ""
    message: str = ""


@router.get("/plans", tags=["Billing"], summary="List available plans")
async def list_plans(_user_id: str = Depends(require_current_user)):
    return {"plans": list(plans.PLANS.values())}


@router.get("/subscription", tags=["Billing"], summary="Current plan")
async def subscription(user_id: str = Depends(require_current_user)):
    from utils import quota  # local import avoids a utils.quota → billing cycle at module load

    plan = billing_store.get_plan(redis_client, user_id)
    return {
        "plan": plan,
        "quota_bytes": plans.quota_for(plan),
        "ai_questions_used_today": quota.get_ai_questions_used_today(redis_client, user_id),
        "ai_questions_per_day": plans.ai_questions_per_day_for(plan),
        "ai_unlimited_plan_wide": plans.PLANS.get(plan, {}).get("ai_unlimited_plan_wide", False),
        # Lets the frontend gate plan-restricted UI (e.g. webhooks) against the
        # same feature flags billing/plans.py already defines as the source
        # of truth, instead of hardcoding "webhooks require Pro+" client-side.
        "features": plans.features_for(plan),
    }


@router.post("/checkout", tags=["Billing"], summary="Upgrade/switch plan (stub — no payment)")
async def checkout(body: CheckoutRequest, user_id: str = Depends(require_current_user)):
    if not plans.is_valid_plan(body.plan):
        raise HTTPException(status_code=400, detail=f"Unknown plan '{body.plan}'")
    if not plans.is_self_serve(body.plan):
        # Customize is a contact-us tier — provisioned manually after a sales
        # conversation, never self-serve. Point the client at the lead form.
        raise HTTPException(
            status_code=400,
            detail=f"The '{body.plan}' plan is available by request only — please contact us.",
        )
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


@router.post("/contact", tags=["Billing"], summary="Submit a Customize-plan enquiry")
async def contact(
    body: ContactRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_current_user),
):
    """
    Capture a 'Customize' plan enquiry: persist the lead (for the admin panel)
    and email the operator (``ADMIN_EMAIL``) so they can follow up. Emailing is
    best-effort and runs in the background — the lead is saved regardless.
    """
    lead = billing_store.add_contact_lead(
        redis_client, body.name, body.email, body.company, body.message, user_id=user_id,
    )
    if config.ADMIN_EMAIL:
        background_tasks.add_task(email_service.send_contact_lead_email, config.ADMIN_EMAIL, lead)
    else:
        logger.warning("Contact lead received but ADMIN_EMAIL is unset — not emailed (still stored)")
    return {"status": "received"}
