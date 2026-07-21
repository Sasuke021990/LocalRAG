"""
Plan catalog for the (stubbed) billing system.

This is a **stub** for Stripe billing: upgrading changes the user's plan and
storage quota immediately, with no real payment or Stripe integration. When
real billing lands, the plan/quota mapping here stays and only the
"payment happened" gate in ``routes.py`` gets replaced with Stripe.

Prices are placeholders and are never charged in the stub.
"""

GB = 1024 ** 3

PLANS = {
    "free": {"id": "free", "name": "Free", "price_cents": 0, "quota_bytes": 1 * GB},
    "pro": {"id": "pro", "name": "Pro", "price_cents": 900, "quota_bytes": 25 * GB},
    "business": {"id": "business", "name": "Business", "price_cents": 2900, "quota_bytes": 250 * GB},
}

DEFAULT_PLAN = "free"


def is_valid_plan(plan: str) -> bool:
    return plan in PLANS


def quota_for(plan: str) -> int:
    return PLANS.get(plan, PLANS[DEFAULT_PLAN])["quota_bytes"]
