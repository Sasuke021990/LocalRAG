"""Tests for auth.google_oauth and the password-reset / Google OAuth routes."""

import pytest
from fastapi import HTTPException

from auth import google_oauth, passwords, store


class _FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data
        self.text = str(json_data)

    def json(self):
        return self._json


class TestExchangeCodeForUserinfo:
    def test_success(self, monkeypatch):
        def fake_post(url, data=None, timeout=None):
            assert url == google_oauth.TOKEN_ENDPOINT
            return _FakeResponse(200, {"access_token": "fake-access-token"})

        def fake_get(url, headers=None, timeout=None):
            assert url == google_oauth.USERINFO_ENDPOINT
            assert headers["Authorization"] == "Bearer fake-access-token"
            return _FakeResponse(200, {"sub": "google-sub-123", "email": "user@example.com"})

        monkeypatch.setattr(google_oauth.requests, "post", fake_post)
        monkeypatch.setattr(google_oauth.requests, "get", fake_get)

        result = google_oauth.exchange_code_for_userinfo("some-code")
        assert result == {"sub": "google-sub-123", "email": "user@example.com"}

    def test_token_exchange_failure_raises(self, monkeypatch):
        monkeypatch.setattr(
            google_oauth.requests, "post",
            lambda *a, **k: _FakeResponse(400, {"error": "invalid_grant"}),
        )
        with pytest.raises(HTTPException) as exc_info:
            google_oauth.exchange_code_for_userinfo("bad-code")
        assert exc_info.value.status_code == 400

    def test_userinfo_fetch_failure_raises(self, monkeypatch):
        monkeypatch.setattr(
            google_oauth.requests, "post",
            lambda *a, **k: _FakeResponse(200, {"access_token": "fake-access-token"}),
        )
        monkeypatch.setattr(
            google_oauth.requests, "get",
            lambda *a, **k: _FakeResponse(401, {"error": "invalid_token"}),
        )
        with pytest.raises(HTTPException) as exc_info:
            google_oauth.exchange_code_for_userinfo("some-code")
        assert exc_info.value.status_code == 400

    def test_build_authorization_url_includes_state(self):
        url = google_oauth.build_authorization_url("csrf-state-value")
        assert "csrf-state-value" in url
        assert url.startswith(google_oauth.AUTHORIZATION_ENDPOINT)


class TestPasswordResetRoutes:
    def test_request_always_returns_ok_even_for_unknown_email(self, auth_client):
        resp = auth_client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_request_for_known_email_returns_ok(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "reset-me@example.com", "password": "longenough123"})
        resp = auth_client.post("/auth/password-reset/request", json={"email": "reset-me@example.com"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_confirm_invalid_token_400(self, auth_client):
        resp = auth_client.post(
            "/auth/password-reset/confirm",
            json={"token": "not-a-real-token", "new_password": "longenough123"},
        )
        assert resp.status_code == 400

    def test_confirm_updates_password_and_bumps_token_version(self, auth_client, redis_client):
        auth_client.post("/auth/signup", json={"email": "reset2@example.com", "password": "originalpass123"})
        user = store.get_user_by_email(redis_client, "reset2@example.com")
        assert user["token_version"] == 0

        token = store.create_password_reset_token(redis_client, user["user_id"])
        resp = auth_client.post(
            "/auth/password-reset/confirm",
            json={"token": token, "new_password": "brandnewpass456"},
        )
        assert resp.status_code == 200

        updated = store.get_user_by_id(redis_client, user["user_id"])
        assert updated["token_version"] == 1
        assert passwords.verify_password("brandnewpass456", updated["password_hash"])
        assert not passwords.verify_password("originalpass123", updated["password_hash"])

    def test_confirm_invalidates_existing_session(self, auth_client, redis_client):
        signup = auth_client.post("/auth/signup", json={"email": "reset3@example.com", "password": "originalpass123"})
        assert auth_client.get("/auth/me").status_code == 200

        user = store.get_user_by_email(redis_client, "reset3@example.com")
        token = store.create_password_reset_token(redis_client, user["user_id"])
        auth_client.post(
            "/auth/password-reset/confirm",
            json={"token": token, "new_password": "brandnewpass456"},
        )

        # The old session cookie (issued with token_version=0) must now be rejected.
        assert auth_client.get("/auth/me").status_code == 401


class TestGoogleCallback:
    def test_links_existing_email_account_instead_of_duplicating(self, auth_client, redis_client, monkeypatch):
        """A user who signed up with a password, then uses Google with the
        same email, should get google_sub linked to their existing
        account -- not a second account."""
        auth_client.post("/auth/signup", json={"email": "linked@example.com", "password": "longenough123"})
        existing = store.get_user_by_email(redis_client, "linked@example.com")

        monkeypatch.setattr(
            google_oauth, "exchange_code_for_userinfo",
            lambda code: {"sub": "google-sub-456", "email": "linked@example.com"},
        )
        # auth_client's app doesn't follow redirects by default in a way
        # that matters here -- just assert the callback doesn't error and
        # the account was linked, not duplicated.
        resp = auth_client.get("/auth/google/callback", params={"code": "irrelevant"}, follow_redirects=False)
        assert resp.status_code in (302, 307)
        # The redirect MUST carry the session cookie, or the user lands on
        # the frontend still logged out (regression guard).
        assert "set-cookie" in {k.lower() for k in resp.headers}

        relinked = store.get_user_by_google_sub(redis_client, "google-sub-456")
        assert relinked["user_id"] == existing["user_id"]
        assert relinked["password_hash"]  # original password preserved

    def test_creates_new_user_for_unseen_email(self, auth_client, redis_client, monkeypatch):
        monkeypatch.setattr(
            google_oauth, "exchange_code_for_userinfo",
            lambda code: {"sub": "google-sub-789", "email": "brandnew@example.com"},
        )
        resp = auth_client.get("/auth/google/callback", params={"code": "irrelevant"}, follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert "set-cookie" in {k.lower() for k in resp.headers}

        created = store.get_user_by_google_sub(redis_client, "google-sub-789")
        assert created is not None
        assert created["email"] == "brandnew@example.com"

        # The cookie set by the redirect must actually authenticate the
        # session -- the point of logging in at all.
        me = auth_client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "brandnew@example.com"
