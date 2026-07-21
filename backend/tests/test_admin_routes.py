"""
HTTP-level tests for /admin/* via the ``api_client`` fixture.

Multi-user control uses explicit Bearer session tokens (the shared cookie
jar would be overwritten by each signup), and the env-admin is designated
by monkeypatching ``config.ADMIN_EMAIL``.
"""

import pytest

from utils.config import config


def _signup(api_client, email):
    """Sign up and return that user's (user_id, session_token)."""
    resp = api_client.post("/auth/signup", json={"email": email, "password": "longenough123"})
    assert resp.status_code == 200
    body = resp.json()
    api_client.cookies.clear()  # force explicit-bearer auth, not the shared cookie
    return body["user_id"], body["session_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(api_client, monkeypatch):
    """Designate root@example.com as the env admin and sign them in."""
    monkeypatch.setattr(config, "ADMIN_EMAIL", "root@example.com")
    user_id, token = _signup(api_client, "root@example.com")
    return {"user_id": user_id, "token": token}


class TestAuthorization:
    def test_non_admin_gets_403(self, api_client, monkeypatch):
        monkeypatch.setattr(config, "ADMIN_EMAIL", "root@example.com")
        _, token = _signup(api_client, "regular@example.com")
        assert api_client.get("/admin/users", headers=_auth(token)).status_code == 403

    def test_unauthenticated_401(self, api_client):
        assert api_client.get("/admin/users").status_code == 401

    def test_api_token_rejected_on_admin_route(self, api_client, admin):
        # Mint an MCP token as the admin, then try to use it on an admin route.
        token_resp = api_client.post(
            "/integrations/tokens", json={"name": "cli"}, headers=_auth(admin["token"])
        )
        mcp_token = token_resp.json()["token"]
        resp = api_client.get("/admin/users", headers={"Authorization": f"Bearer {mcp_token}"})
        assert resp.status_code == 401

    def test_env_admin_access_self_heals_is_admin_flag(self, api_client, admin, redis_client):
        # Before any admin request the flag may be 0; after one it must be 1.
        assert api_client.get("/admin/stats", headers=_auth(admin["token"])).status_code == 200
        assert redis_client.hget(f"user:{admin['user_id']}", "is_admin") == "1"

    def test_me_exposes_is_admin(self, api_client, admin):
        # The env-admin's /auth/me reports is_admin so the UI can show admin nav.
        assert api_client.get("/auth/me", headers=_auth(admin["token"])).json()["is_admin"] is True

    def test_me_non_admin_is_false(self, api_client, monkeypatch):
        monkeypatch.setattr(config, "ADMIN_EMAIL", "root@example.com")
        _, token = _signup(api_client, "plain@example.com")
        assert api_client.get("/auth/me", headers=_auth(token)).json()["is_admin"] is False


class TestUserManagement:
    def test_list_and_get_user(self, api_client, admin):
        target_id, _ = _signup(api_client, "target@example.com")
        listed = api_client.get("/admin/users", headers=_auth(admin["token"])).json()
        emails = {u["email"] for u in listed["users"]}
        assert {"root@example.com", "target@example.com"} <= emails

        detail = api_client.get(f"/admin/users/{target_id}", headers=_auth(admin["token"]))
        assert detail.status_code == 200
        assert detail.json()["token_count"] == 0

    def test_get_missing_user_404(self, api_client, admin):
        assert api_client.get("/admin/users/nope", headers=_auth(admin["token"])).status_code == 404

    def test_update_quota(self, api_client, admin):
        target_id, target_token = _signup(api_client, "target@example.com")
        resp = api_client.patch(
            f"/admin/users/{target_id}/quota", json={"quota_bytes": 5_000_000}, headers=_auth(admin["token"])
        )
        assert resp.status_code == 200
        assert resp.json()["storage_quota_bytes"] == 5_000_000
        # Reflected in the target's own /auth/me.
        me = api_client.get("/auth/me", headers=_auth(target_token)).json()
        assert me["storage_quota_bytes"] == 5_000_000

    def test_negative_quota_422(self, api_client, admin):
        target_id, _ = _signup(api_client, "target@example.com")
        resp = api_client.patch(
            f"/admin/users/{target_id}/quota", json={"quota_bytes": -1}, headers=_auth(admin["token"])
        )
        assert resp.status_code == 422

    def test_deactivate_blocks_target_session(self, api_client, admin):
        target_id, target_token = _signup(api_client, "target@example.com")
        # Target works before.
        assert api_client.get("/probe", headers=_auth(target_token)).status_code == 200
        # Admin deactivates.
        api_client.patch(
            f"/admin/users/{target_id}/status", json={"is_active": False}, headers=_auth(admin["token"])
        )
        # Target's session is now rejected (403 account disabled).
        assert api_client.get("/probe", headers=_auth(target_token)).status_code == 403

    def test_promote_and_demote_admin(self, api_client, admin):
        target_id, target_token = _signup(api_client, "target@example.com")
        # Promote -> target can now hit admin routes.
        api_client.patch(
            f"/admin/users/{target_id}/admin", json={"is_admin": True}, headers=_auth(admin["token"])
        )
        assert api_client.get("/admin/stats", headers=_auth(target_token)).status_code == 200
        # Demote -> back to 403.
        api_client.patch(
            f"/admin/users/{target_id}/admin", json={"is_admin": False}, headers=_auth(admin["token"])
        )
        assert api_client.get("/admin/stats", headers=_auth(target_token)).status_code == 403

    def test_delete_user_cascade(self, api_client, admin):
        target_id, _ = _signup(api_client, "target@example.com")
        resp = api_client.delete(f"/admin/users/{target_id}", headers=_auth(admin["token"]))
        assert resp.status_code == 200
        listed = api_client.get("/admin/users", headers=_auth(admin["token"])).json()
        assert all(u["user_id"] != target_id for u in listed["users"])


class TestSelfProtection:
    def test_cannot_delete_self(self, api_client, admin):
        resp = api_client.delete(f"/admin/users/{admin['user_id']}", headers=_auth(admin["token"]))
        assert resp.status_code == 400

    def test_cannot_deactivate_root_admin(self, api_client, admin):
        resp = api_client.patch(
            f"/admin/users/{admin['user_id']}/status", json={"is_active": False}, headers=_auth(admin["token"])
        )
        assert resp.status_code == 400

    def test_cannot_demote_root_admin(self, api_client, admin):
        resp = api_client.patch(
            f"/admin/users/{admin['user_id']}/admin", json={"is_admin": False}, headers=_auth(admin["token"])
        )
        assert resp.status_code == 400


class TestSettings:
    def test_get_settings(self, api_client, admin):
        resp = api_client.get("/admin/settings", headers=_auth(admin["token"]))
        assert resp.status_code == 200
        assert "signups_enabled" in resp.json()["settings"]

    def test_disable_signups_blocks_signup(self, api_client, admin):
        api_client.patch(
            "/admin/settings", json={"name": "signups_enabled", "value": False}, headers=_auth(admin["token"])
        )
        resp = api_client.post("/auth/signup", json={"email": "late@example.com", "password": "longenough123"})
        assert resp.status_code == 403

    def test_unknown_setting_400(self, api_client, admin):
        resp = api_client.patch(
            "/admin/settings", json={"name": "bogus", "value": 1}, headers=_auth(admin["token"])
        )
        assert resp.status_code == 400
