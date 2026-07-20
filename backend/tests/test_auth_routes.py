"""
HTTP-level tests for /auth/* routes and the require_current_user gate on
existing routes.

Importing ``main`` constructs the full app, including
DocumentIngestionPipeline/HybridSearchEngine, which call
vector_index.ensure_index() at construction time — that requires a
RediSearch build with VECTOR field support (redis-stack), same
requirement as tests/test_vector_index.py. Skips cleanly without it (e.g.
a plain redis-server locally); CI runs these against a redis-stack
service container.
"""

import pytest

from tests.conftest import REDIS_HOST, REDIS_PORT


@pytest.fixture
def client(redis_client, redisearch_vector_available):
    if not redisearch_vector_available:
        pytest.skip("RediSearch VECTOR field support not available (needs redis-stack)")

    from fastapi.testclient import TestClient

    import main as main_module

    return TestClient(main_module.app)


class TestSignupLoginMe:
    def test_signup_then_me_returns_user(self, client):
        resp = client.post("/auth/signup", json={"email": "alice@example.com", "password": "longenough123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "alice@example.com"
        assert body["storage_used_bytes"] == 0
        assert "session_token" in body

        me = client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "alice@example.com"

    def test_signup_short_password_422(self, client):
        resp = client.post("/auth/signup", json={"email": "bob@example.com", "password": "short"})
        assert resp.status_code == 422

    def test_signup_duplicate_email_409(self, client):
        client.post("/auth/signup", json={"email": "carol@example.com", "password": "longenough123"})
        resp = client.post("/auth/signup", json={"email": "carol@example.com", "password": "otherpassword"})
        assert resp.status_code == 409

    def test_login_wrong_password_401(self, client):
        client.post("/auth/signup", json={"email": "dave@example.com", "password": "longenough123"})
        resp = client.post("/auth/login", json={"email": "dave@example.com", "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_login_unknown_email_401(self, client):
        resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "longenough123"})
        assert resp.status_code == 401

    def test_login_sets_cookie_and_me_works(self, client):
        client.post("/auth/signup", json={"email": "eve@example.com", "password": "longenough123"})
        client.cookies.clear()  # exercise a fresh login, not the signup session

        resp = client.post("/auth/login", json={"email": "eve@example.com", "password": "longenough123"})
        assert resp.status_code == 200

        me = client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "eve@example.com"

    def test_login_response_includes_session_token(self, client):
        client.post("/auth/signup", json={"email": "frank@example.com", "password": "longenough123"})
        client.cookies.clear()
        resp = client.post("/auth/login", json={"email": "frank@example.com", "password": "longenough123"})
        assert resp.json()["session_token"]


class TestLogout:
    def test_logout_clears_cookie_then_me_401(self, client):
        client.post("/auth/signup", json={"email": "grace@example.com", "password": "longenough123"})
        assert client.get("/auth/me").status_code == 200

        logout = client.post("/auth/logout")
        assert logout.status_code == 200

        assert client.get("/auth/me").status_code == 401


class TestProtectedRoutes:
    def test_protected_route_without_session_401(self, client):
        assert client.get("/documents").status_code == 401

    def test_root_and_health_do_not_require_auth(self, client):
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 200

    def test_bearer_token_auth_works_without_cookie(self, client):
        signup = client.post("/auth/signup", json={"email": "heidi@example.com", "password": "longenough123"})
        token = signup.json()["session_token"]
        client.cookies.clear()

        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "heidi@example.com"

    def test_protected_route_with_bearer_token_succeeds(self, client):
        signup = client.post("/auth/signup", json={"email": "ivan@example.com", "password": "longenough123"})
        token = signup.json()["session_token"]
        client.cookies.clear()

        resp = client.get("/documents", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
