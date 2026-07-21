"""Redis reads/writes for a user's billing plan (stored on the user:<id> HASH)."""

import logging

from billing import plans

logger = logging.getLogger(__name__)


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
