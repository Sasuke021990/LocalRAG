"""Redis reads/writes for a user's billing plan (stored on the user:<id> HASH),
plus Customize-plan contact leads."""

import json
import logging
import uuid
from datetime import datetime

from billing import plans

logger = logging.getLogger(__name__)

_LEAD_INDEX = "contact_leads"  # a Redis LIST of lead JSON blobs, newest first


def _user_key(user_id: str) -> str:
    return f"user:{user_id}"


def get_plan(redis_client, user_id: str) -> str:
    value = redis_client.hget(_user_key(user_id), "plan")
    return value if value in plans.PLANS else plans.DEFAULT_PLAN


def set_plan(redis_client, user_id: str, plan: str) -> None:
    """
    Set the user's plan and reset their storage quota to that plan's
    allowance. Raises ValueError for an unknown plan. (Stub: no payment.)
    """
    if not plans.is_valid_plan(plan):
        raise ValueError(f"unknown plan: {plan}")
    redis_client.hset(_user_key(user_id), mapping={
        "plan": plan,
        "storage_quota_bytes": plans.quota_for(plan),
    })
    logger.info(f"[billing-stub] user {user_id} → plan '{plan}' (quota {plans.quota_for(plan)} bytes)")


def add_contact_lead(redis_client, name: str, email: str, company: str, message: str, user_id: str = "") -> dict:
    """Persist a Customize-plan enquiry (newest first) and return the stored lead."""
    lead = {
        "id": uuid.uuid4().hex,
        "name": name,
        "email": email,
        "company": company,
        "message": message,
        "user_id": user_id,
        "created_at": datetime.now().isoformat(),
    }
    redis_client.lpush(_LEAD_INDEX, json.dumps(lead))
    logger.info(f"Stored contact lead {lead['id']} from {email}")
    return lead


def list_contact_leads(redis_client, limit: int = 100) -> list:
    """Return recent contact leads, newest first (for the admin panel)."""
    raw = redis_client.lrange(_LEAD_INDEX, 0, limit - 1)
    leads = []
    for item in raw:
        try:
            leads.append(json.loads(item))
        except Exception:
            continue
    return leads
