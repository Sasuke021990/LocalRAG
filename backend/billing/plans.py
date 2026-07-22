"""
Plan catalog — the single source of truth for plan pricing, quotas, and
feature gating.

This is still a **stub** for real payment: self-serve upgrades change the
user's plan and storage quota immediately, with no payment processor wired
in yet (see ``routes.py``). All the numbers below come from ``Config`` so they
are env-configurable; only the "payment happened" gate is missing.

Tiers (INR):
  free      — 1 GB, 10 AI Q/day
  pro       — 5 GB, 25 AI Q/day, webhooks, priority processing
  max       — 15 GB, 30 AI Q/user/day (unlimited plan-wide), team sharing
  customize — contact-us only (no self-serve checkout); values set per customer
"""

from utils.config import config

GB = 1024 ** 3

# Feature flags are the single source of truth for gating: enforce every
# capability (webhooks, priority queue, team sharing) against these, not
# against what's merely technically possible.
PLANS = {
    "free": {
        "id": "free",
        "name": "Free",
        "price_inr_monthly": 0,
        "price_inr_annual": 0,
        "quota_bytes": config.FREE_STORAGE_GB * GB,
        "storage_gb": config.FREE_STORAGE_GB,
        "ai_questions_per_day": config.FREE_AI_QUESTIONS_PER_DAY,
        "ai_unlimited_plan_wide": False,
        "contact_only": False,
        "features": {
            "pools": True,
            "hybrid_chat": True,
            "api_tokens": True,
            "webhooks": False,
            "priority_processing": False,
            "team_members": 0,
        },
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price_inr_monthly": config.PRO_PRICE_MONTHLY_INR,
        "price_inr_annual": config.PRO_PRICE_ANNUAL_INR,
        "quota_bytes": config.PRO_STORAGE_GB * GB,
        "storage_gb": config.PRO_STORAGE_GB,
        "ai_questions_per_day": config.PRO_AI_QUESTIONS_PER_DAY,
        "ai_unlimited_plan_wide": False,
        "contact_only": False,
        "features": {
            "pools": True,
            "hybrid_chat": True,
            "api_tokens": True,
            "webhooks": True,
            "priority_processing": True,
            "team_members": 0,
        },
    },
    "max": {
        "id": "max",
        "name": "Max",
        "price_inr_monthly": config.MAX_PRICE_MONTHLY_INR,
        "price_inr_annual": config.MAX_PRICE_ANNUAL_INR,
        "quota_bytes": config.MAX_STORAGE_GB * GB,
        "storage_gb": config.MAX_STORAGE_GB,
        # Per-user daily cap; the plan itself is "unlimited" plan-wide.
        "ai_questions_per_day": config.MAX_AI_QUESTIONS_PER_DAY_PER_USER,
        "ai_unlimited_plan_wide": True,
        "contact_only": False,
        "features": {
            "pools": True,
            "hybrid_chat": True,
            "api_tokens": True,
            "webhooks": True,
            "priority_processing": True,
            "team_members": config.MAX_PLAN_TEAM_MEMBERS,
        },
    },
    "customize": {
        "id": "customize",
        "name": "Customize",
        # No fixed price — a contact-us tier, negotiated per customer.
        "price_inr_monthly": None,
        "price_inr_annual": None,
        # Placeholder allowances (mirror Max) until set manually per customer.
        "quota_bytes": config.MAX_STORAGE_GB * GB,
        "storage_gb": config.MAX_STORAGE_GB,
        "ai_questions_per_day": config.MAX_AI_QUESTIONS_PER_DAY_PER_USER,
        "ai_unlimited_plan_wide": True,
        "contact_only": True,
        "features": {
            "pools": True,
            "hybrid_chat": True,
            "api_tokens": True,
            "webhooks": True,
            "priority_processing": True,
            "team_members": None,  # negotiated
        },
    },
}

DEFAULT_PLAN = "free"

# Plans a user can self-serve checkout into. Customize is contact-only and is
# provisioned manually after a sales conversation, never via /billing/checkout.
SELF_SERVE_PLANS = ("free", "pro", "max")


def is_valid_plan(plan: str) -> bool:
    return plan in PLANS


def is_self_serve(plan: str) -> bool:
    """True if a user can switch to this plan themselves (not contact-only)."""
    return plan in SELF_SERVE_PLANS


def quota_for(plan: str) -> int:
    return PLANS.get(plan, PLANS[DEFAULT_PLAN])["quota_bytes"]


def ai_questions_per_day_for(plan: str) -> int:
    """Per-user daily AI-question allowance for a plan."""
    return PLANS.get(plan, PLANS[DEFAULT_PLAN])["ai_questions_per_day"]


def features_for(plan: str) -> dict:
    return PLANS.get(plan, PLANS[DEFAULT_PLAN])["features"]


def has_feature(plan: str, feature: str) -> bool:
    """True if the plan enables a boolean feature flag (e.g. 'webhooks')."""
    return bool(features_for(plan).get(feature))
