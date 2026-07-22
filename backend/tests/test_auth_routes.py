"""
HTTP-level tests for /auth/* routes and the require_current_user gate,
via the ``auth_client`` fixture (conftest.py) — a minimal app mounting
only the real auth router, so these run against a plain Redis (no
redis-stack/RediSearch needed, unlike main.py's full app).
"""


class TestSignupLoginMe:
    def test_signup_then_me_returns_user(self, auth_client):
        resp = auth_client.post("/auth/signup", json={"email": "alice@example.com", "password": "longenough123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "alice@example.com"
        assert body["storage_used_bytes"] == 0
        assert "session_token" in body

        me = auth_client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "alice@example.com"

    def test_signup_short_password_422(self, auth_client):
        resp = auth_client.post("/auth/signup", json={"email": "bob@example.com", "password": "short"})
        assert resp.status_code == 422

    def test_signup_duplicate_email_409(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "carol@example.com", "password": "longenough123"})
        resp = auth_client.post("/auth/signup", json={"email": "carol@example.com", "password": "otherpassword"})
        assert resp.status_code == 409

    def test_signup_captures_username(self, auth_client):
        resp = auth_client.post(
            "/auth/signup",
            json={"username": "Alice W", "email": "aliceusername@example.com", "password": "longenough123"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "Alice W"
        assert auth_client.get("/auth/me").json()["username"] == "Alice W"

    def test_signup_without_username_falls_back_to_email_local_part(self, auth_client):
        resp = auth_client.post(
            "/auth/signup", json={"email": "nouser@example.com", "password": "longenough123"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "nouser"

    def test_login_wrong_password_401(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "dave@example.com", "password": "longenough123"})
        resp = auth_client.post("/auth/login", json={"email": "dave@example.com", "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_login_unknown_email_401(self, auth_client):
        resp = auth_client.post("/auth/login", json={"email": "nobody@example.com", "password": "longenough123"})
        assert resp.status_code == 401

    def test_login_sets_cookie_and_me_works(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "eve@example.com", "password": "longenough123"})
        auth_client.cookies.clear()  # exercise a fresh login, not the signup session

        resp = auth_client.post("/auth/login", json={"email": "eve@example.com", "password": "longenough123"})
        assert resp.status_code == 200

        me = auth_client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "eve@example.com"

    def test_login_response_includes_session_token(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "frank@example.com", "password": "longenough123"})
        auth_client.cookies.clear()
        resp = auth_client.post("/auth/login", json={"email": "frank@example.com", "password": "longenough123"})
        assert resp.json()["session_token"]


class TestChangePassword:
    def test_change_password_success_keeps_session(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "cp@example.com", "password": "originalpass1"})
        resp = auth_client.post(
            "/auth/change-password",
            json={"current_password": "originalpass1", "new_password": "brandnewpass2"},
        )
        assert resp.status_code == 200
        # Current client stays logged in (re-issued a fresh cookie).
        assert auth_client.get("/auth/me").status_code == 200
        # New password works, old one doesn't.
        auth_client.post("/auth/logout")
        assert auth_client.post("/auth/login", json={"email": "cp@example.com", "password": "brandnewpass2"}).status_code == 200
        assert auth_client.post("/auth/login", json={"email": "cp@example.com", "password": "originalpass1"}).status_code == 401

    def test_change_password_wrong_current_400(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "cp2@example.com", "password": "originalpass1"})
        resp = auth_client.post(
            "/auth/change-password",
            json={"current_password": "wrongcurrent", "new_password": "brandnewpass2"},
        )
        assert resp.status_code == 400

    def test_change_password_requires_auth(self, auth_client):
        resp = auth_client.post(
            "/auth/change-password",
            json={"current_password": "x", "new_password": "brandnewpass2"},
        )
        assert resp.status_code == 401


class TestLogout:
    def test_logout_clears_cookie_then_me_401(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "grace@example.com", "password": "longenough123"})
        assert auth_client.get("/auth/me").status_code == 200

        logout = auth_client.post("/auth/logout")
        assert logout.status_code == 200

        assert auth_client.get("/auth/me").status_code == 401


class TestProtectedRoutes:
    def test_protected_route_without_session_401(self, auth_client):
        assert auth_client.get("/protected").status_code == 401

    def test_bearer_token_auth_works_without_cookie(self, auth_client):
        signup = auth_client.post("/auth/signup", json={"email": "heidi@example.com", "password": "longenough123"})
        token = signup.json()["session_token"]
        auth_client.cookies.clear()

        resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "heidi@example.com"

    def test_protected_route_with_bearer_token_succeeds(self, auth_client):
        signup = auth_client.post("/auth/signup", json={"email": "ivan@example.com", "password": "longenough123"})
        token = signup.json()["session_token"]
        auth_client.cookies.clear()

        resp = auth_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["user_id"]
