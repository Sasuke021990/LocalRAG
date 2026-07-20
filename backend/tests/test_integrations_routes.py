"""
HTTP-level tests for /integrations/* (tokens + webhooks) via the
``api_client`` fixture, plus the token-auth-vs-session-only boundary.
"""


def _signup(api_client, email="user@example.com"):
    resp = api_client.post("/auth/signup", json={"email": email, "password": "longenough123"})
    assert resp.status_code == 200
    return resp.json()


class TestTokenManagement:
    def test_create_list_revoke(self, api_client):
        _signup(api_client)

        created = api_client.post("/integrations/tokens", json={"name": "my-laptop"})
        assert created.status_code == 200
        body = created.json()
        assert body["token"].startswith("vlt_")
        assert body["name"] == "my-laptop"
        token_id = body["token_id"]

        listed = api_client.get("/integrations/tokens").json()
        assert listed["total"] == 1
        # Listing must never echo the plaintext token.
        assert "token" not in listed["tokens"][0]
        assert listed["tokens"][0]["prefix"] == body["prefix"]

        revoked = api_client.delete(f"/integrations/tokens/{token_id}")
        assert revoked.status_code == 200
        assert api_client.get("/integrations/tokens").json()["total"] == 0

    def test_revoke_unknown_404(self, api_client):
        _signup(api_client)
        assert api_client.delete("/integrations/tokens/nope").status_code == 404

    def test_create_requires_auth(self, api_client):
        assert api_client.post("/integrations/tokens", json={"name": "x"}).status_code == 401

    def test_short_name_422(self, api_client):
        _signup(api_client)
        assert api_client.post("/integrations/tokens", json={"name": ""}).status_code == 422


class TestTokenAuthBoundary:
    def test_token_authenticates_data_route_but_not_management(self, api_client):
        _signup(api_client)
        token = api_client.post("/integrations/tokens", json={"name": "cli"}).json()["token"]
        api_client.cookies.clear()  # drop the session -- rely purely on the token

        # require_current_user route: token works.
        probe = api_client.get("/probe", headers={"Authorization": f"Bearer {token}"})
        assert probe.status_code == 200
        assert probe.json()["user_id"]

        # require_session_user route: token is rejected (privilege containment).
        mint = api_client.post(
            "/integrations/tokens",
            json={"name": "second"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert mint.status_code == 401


class TestWebhookManagement:
    def test_create_list_delete(self, api_client):
        _signup(api_client)

        created = api_client.post(
            "/integrations/webhooks",
            json={"url": "https://example.com/hook", "events": ["document.ingested"]},
        )
        assert created.status_code == 200
        wh = created.json()
        assert wh["secret"]
        assert wh["events"] == ["document.ingested"]
        webhook_id = wh["webhook_id"]

        listed = api_client.get("/integrations/webhooks").json()
        assert listed["total"] == 1

        assert api_client.delete(f"/integrations/webhooks/{webhook_id}").status_code == 200
        assert api_client.get("/integrations/webhooks").json()["total"] == 0

    def test_create_unsupported_event_400(self, api_client):
        _signup(api_client)
        resp = api_client.post(
            "/integrations/webhooks",
            json={"url": "https://example.com/hook", "events": ["bogus.event"]},
        )
        assert resp.status_code == 400

    def test_create_bad_url_422(self, api_client):
        _signup(api_client)
        resp = api_client.post(
            "/integrations/webhooks",
            json={"url": "ftp://nope", "events": ["document.ingested"]},
        )
        assert resp.status_code == 422

    def test_test_endpoint_queues_for_known_webhook(self, api_client, monkeypatch):
        # TestClient runs the BackgroundTask synchronously after the response,
        # so stub out the actual HTTP delivery to keep this offline/fast.
        from integrations import webhooks as webhooks_module

        class _Resp:
            status_code = 200

        monkeypatch.setattr(webhooks_module.requests, "post", lambda *a, **k: _Resp())

        _signup(api_client)
        wh = api_client.post(
            "/integrations/webhooks",
            json={"url": "https://example.com/hook", "events": ["document.ingested"]},
        ).json()
        resp = api_client.post(f"/integrations/webhooks/{wh['webhook_id']}/test")
        assert resp.status_code == 200
        assert resp.json()["status"] == "test_queued"

    def test_test_endpoint_unknown_webhook_404(self, api_client):
        _signup(api_client)
        assert api_client.post("/integrations/webhooks/nope/test").status_code == 404

    def test_webhooks_require_auth(self, api_client):
        assert api_client.get("/integrations/webhooks").status_code == 401
