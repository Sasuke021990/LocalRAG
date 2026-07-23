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

    def test_signup_and_me_expose_idle_timeout(self, auth_client):
        from utils.config import config
        resp = auth_client.post(
            "/auth/signup", json={"email": "idletest@example.com", "password": "longenough123"},
        )
        assert resp.json()["idle_timeout_seconds"] == config.SESSION_IDLE_TIMEOUT_SECONDS
        me = auth_client.get("/auth/me")
        assert me.json()["idle_timeout_seconds"] == config.SESSION_IDLE_TIMEOUT_SECONDS

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

    def test_login_by_username(self, auth_client):
        auth_client.post(
            "/auth/signup",
            json={"username": "kelly_k", "email": "kelly@example.com", "password": "longenough123"},
        )
        auth_client.cookies.clear()
        resp = auth_client.post("/auth/login", json={"email": "kelly_k", "password": "longenough123"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "kelly@example.com"

    def test_login_by_username_case_insensitive(self, auth_client):
        auth_client.post(
            "/auth/signup",
            json={"username": "LeoLion", "email": "leo@example.com", "password": "longenough123"},
        )
        auth_client.cookies.clear()
        resp = auth_client.post("/auth/login", json={"email": "leolion", "password": "longenough123"})
        assert resp.status_code == 200

    def test_login_unknown_username_401(self, auth_client):
        resp = auth_client.post("/auth/login", json={"email": "no-such-username", "password": "longenough123"})
        assert resp.status_code == 401

    def test_signup_duplicate_username_409(self, auth_client):
        auth_client.post(
            "/auth/signup", json={"username": "mona", "email": "mona1@example.com", "password": "longenough123"},
        )
        resp = auth_client.post(
            "/auth/signup", json={"username": "mona", "email": "mona2@example.com", "password": "longenough123"},
        )
        assert resp.status_code == 409
        assert "username" in resp.json()["detail"].lower()

    def test_signup_duplicate_email_error_mentions_email_not_username(self, auth_client):
        auth_client.post("/auth/signup", json={"email": "nolan@example.com", "password": "longenough123"})
        resp = auth_client.post("/auth/signup", json={"email": "nolan@example.com", "password": "otherpassword"})
        assert resp.status_code == 409
        assert "email" in resp.json()["detail"].lower()


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

    def test_logout_revokes_the_bearer_token_itself(self, auth_client):
        """
        A stateless JWT would otherwise stay valid until exp even after
        logout -- prove the presented token is actually blacklisted
        server-side (SECURITY.md L3), not just that the cookie is cleared.
        """
        signup = auth_client.post("/auth/signup", json={"email": "ivan@example.com", "password": "longenough123"})
        token = signup.json()["session_token"]

        # Log out via the cookie set at signup.
        assert auth_client.post("/auth/logout").status_code == 200

        # The exact token issued at signup must no longer work, even
        # presented fresh as a bearer header (no cookie involved).
        resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_logout_does_not_revoke_other_sessions(self, auth_client):
        """Logging out one device must not log out a second device's token
        (that's what change-password/reset already do via token_version)."""
        signup = auth_client.post("/auth/signup", json={"email": "judy@example.com", "password": "longenough123"})
        first_token = signup.json()["session_token"]

        login = auth_client.post("/auth/login", json={"email": "judy@example.com", "password": "longenough123"})
        second_token = login.json()["session_token"]

        assert auth_client.post("/auth/logout").status_code == 200  # revokes the cookie's token (2nd login's)

        # The first device's token is untouched.
        resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {first_token}"})
        assert resp.status_code == 200
        assert second_token != first_token


class TestSelfServiceAccountDeletion:
    """
    Uses ``api_client`` (auth + integrations + admin mounted) rather than
    ``auth_client`` so these tests can mint an MCP token to prove it's
    rejected -- self-service deletion must be session-only.
    """

    def test_delete_own_account_removes_everything(self, api_client):
        api_client.post("/auth/signup", json={"email": "karl@example.com", "password": "longenough123"})
        assert api_client.get("/auth/me").status_code == 200

        resp = api_client.request("DELETE", "/auth/me", json={"password": "longenough123"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "account_deleted"

        # Session is gone (cookie cleared + user record no longer exists).
        assert api_client.get("/auth/me").status_code == 401

        # The email is free again -- proves the account was actually removed,
        # not just logged out.
        signup_again = api_client.post("/auth/signup", json={"email": "karl@example.com", "password": "differentpass1"})
        assert signup_again.status_code == 200

    def test_delete_own_account_wrong_password_400(self, api_client):
        api_client.post("/auth/signup", json={"email": "leah@example.com", "password": "longenough123"})
        resp = api_client.request("DELETE", "/auth/me", json={"password": "wrongpassword"})
        assert resp.status_code == 400
        # Account must still exist and be reachable.
        assert api_client.get("/auth/me").status_code == 200

    def test_delete_own_account_requires_auth(self, api_client):
        resp = api_client.request("DELETE", "/auth/me", json={"password": "whatever"})
        assert resp.status_code == 401

    def test_delete_own_account_rejects_mcp_token(self, api_client):
        """A leaked API token must not be able to wipe the account it belongs to."""
        api_client.post("/auth/signup", json={"email": "mallory@example.com", "password": "longenough123"})
        token_resp = api_client.post("/integrations/tokens", json={"name": "ci"})
        assert token_resp.status_code == 200
        mcp_token = token_resp.json()["token"]

        api_client.cookies.clear()
        resp = api_client.request(
            "DELETE", "/auth/me",
            headers={"Authorization": f"Bearer {mcp_token}"},
            json={"password": "longenough123"},
        )
        assert resp.status_code == 401


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
