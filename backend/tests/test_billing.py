"""
Tests for the (stubbed) billing system: the plan catalog, the Redis-backed
plan store, and the /billing/* HTTP endpoints. The stub changes plan + quota
immediately with no payment, so these assert exactly that behavior.
"""

import pytest

from billing import plans
from billing import store as billing_store


class TestPlanCatalog:
    def test_free_is_default_and_valid(self):
        assert plans.DEFAULT_PLAN == "free"
        assert plans.is_valid_plan("free")
        assert plans.is_valid_plan("pro")
        assert plans.is_valid_plan("max")
        assert plans.is_valid_plan("customize")

    def test_unknown_plan_invalid(self):
        assert not plans.is_valid_plan("enterprise")
        assert not plans.is_valid_plan("business")  # renamed to 'max'
        assert not plans.is_valid_plan("")

    def test_quota_increases_with_tier(self):
        assert plans.quota_for("free") < plans.quota_for("pro") < plans.quota_for("max")

    def test_quota_for_unknown_falls_back_to_default(self):
        assert plans.quota_for("nonsense") == plans.quota_for(plans.DEFAULT_PLAN)

    def test_ai_question_limits_per_tier(self):
        assert plans.ai_questions_per_day_for("free") == 10
        assert plans.ai_questions_per_day_for("pro") == 25
        assert plans.ai_questions_per_day_for("max") == 30

    def test_feature_gating_flags(self):
        assert not plans.has_feature("free", "webhooks")
        assert plans.has_feature("pro", "webhooks")
        assert plans.has_feature("max", "priority_processing")
        assert plans.features_for("max")["team_members"] >= 5

    def test_customize_is_contact_only(self):
        assert plans.is_self_serve("free")
        assert plans.is_self_serve("pro")
        assert plans.is_self_serve("max")
        assert not plans.is_self_serve("customize")
        assert plans.PLANS["customize"]["price_inr_monthly"] is None

    def test_conversation_limits_per_tier(self):
        assert plans.conversation_limit_for("free") == 5
        assert plans.conversation_limit_for("pro") == 15
        assert plans.conversation_limit_for("max") == 20

    def test_conversation_limit_for_unknown_falls_back_to_default(self):
        assert plans.conversation_limit_for("nonsense") == plans.conversation_limit_for(plans.DEFAULT_PLAN)


class TestPlanStore:
    def test_new_user_defaults_to_free(self, redis_client, test_user):
        assert billing_store.get_plan(redis_client, test_user) == "free"

    def test_get_plan_unknown_user_defaults_to_free(self, redis_client):
        assert billing_store.get_plan(redis_client, "no-such-user") == "free"

    def test_set_plan_updates_plan_and_quota(self, redis_client, test_user):
        billing_store.set_plan(redis_client, test_user, "pro")
        assert billing_store.get_plan(redis_client, test_user) == "pro"
        stored_quota = int(redis_client.hget(f"user:{test_user}", "storage_quota_bytes"))
        assert stored_quota == plans.quota_for("pro")

    def test_set_plan_rejects_unknown(self, redis_client, test_user):
        with pytest.raises(ValueError):
            billing_store.set_plan(redis_client, test_user, "enterprise")

    def test_downgrade_restores_free_quota(self, redis_client, test_user):
        billing_store.set_plan(redis_client, test_user, "max")
        billing_store.set_plan(redis_client, test_user, "free")
        assert billing_store.get_plan(redis_client, test_user) == "free"
        assert int(redis_client.hget(f"user:{test_user}", "storage_quota_bytes")) == plans.quota_for("free")


@pytest.fixture
def billing_client(redis_client):
    """TestClient mounting the real auth + billing routers (no heavy ML init)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth import routes as auth_routes
    from billing import routes as billing_routes

    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/auth")
    app.include_router(billing_routes.router, prefix="/billing")
    return TestClient(app)


def _signup(client, email="biller@example.com"):
    resp = client.post("/auth/signup", json={"email": email, "password": "longenough123"})
    assert resp.status_code == 200
    return resp.json()


class TestBillingRoutes:
    def test_list_plans(self, billing_client):
        _signup(billing_client)
        body = billing_client.get("/billing/plans").json()
        ids = {p["id"] for p in body["plans"]}
        assert ids == {"free", "pro", "max", "customize"}

    def test_subscription_defaults_to_free(self, billing_client):
        _signup(billing_client)
        body = billing_client.get("/billing/subscription").json()
        assert body["plan"] == "free"
        assert body["quota_bytes"] == plans.quota_for("free")

    def test_subscription_exposes_feature_flags_for_frontend_gating(self, billing_client):
        _signup(billing_client)
        body = billing_client.get("/billing/subscription").json()
        assert body["features"]["webhooks"] is False  # free plan
        billing_client.post("/billing/checkout", json={"plan": "pro"})
        body = billing_client.get("/billing/subscription").json()
        assert body["features"]["webhooks"] is True  # pro plan

    def test_checkout_activates_immediately_as_stub(self, billing_client):
        _signup(billing_client)
        resp = billing_client.post("/billing/checkout", json={"plan": "pro"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "activated"
        assert body["stub"] is True
        assert body["plan"] == "pro"
        assert body["quota_bytes"] == plans.quota_for("pro")
        # And it persists on the subscription read.
        assert billing_client.get("/billing/subscription").json()["plan"] == "pro"

    def test_checkout_rejects_unknown_plan(self, billing_client):
        _signup(billing_client)
        assert billing_client.post("/billing/checkout", json={"plan": "enterprise"}).status_code == 400

    def test_checkout_rejects_contact_only_customize(self, billing_client):
        _signup(billing_client)
        # Customize is a valid plan but not self-serve — checkout must refuse it.
        resp = billing_client.post("/billing/checkout", json={"plan": "customize"})
        assert resp.status_code == 400
        assert billing_client.get("/billing/subscription").json()["plan"] == "free"

    def test_cancel_downgrades_to_free(self, billing_client):
        _signup(billing_client)
        billing_client.post("/billing/checkout", json={"plan": "max"})
        resp = billing_client.post("/billing/cancel")
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"
        assert billing_client.get("/billing/subscription").json()["plan"] == "free"

    def test_billing_requires_auth(self, billing_client):
        assert billing_client.get("/billing/subscription").status_code == 401
        assert billing_client.post("/billing/checkout", json={"plan": "pro"}).status_code == 401

    def test_me_reflects_plan_after_checkout(self, billing_client):
        _signup(billing_client)
        billing_client.post("/billing/checkout", json={"plan": "pro"})
        me = billing_client.get("/auth/me").json()
        assert me["plan"] == "pro"
