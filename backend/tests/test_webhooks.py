"""Tests for integrations.webhooks (store + signed HMAC delivery)."""

import hashlib
import hmac
import json

import pytest

from integrations import webhooks


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class TestStore:
    def test_create_and_get(self, redis_client):
        wh = webhooks.create_webhook(
            redis_client, "user-a", "https://example.com/hook", ["document.ingested"]
        )
        assert wh["url"] == "https://example.com/hook"
        assert wh["events"] == ["document.ingested"]
        assert wh["is_active"] is True
        assert wh["secret"]  # auto-generated
        assert webhooks.get_webhook(redis_client, "user-a", wh["webhook_id"])["url"] == wh["url"]

    def test_create_honors_explicit_secret(self, redis_client):
        wh = webhooks.create_webhook(
            redis_client, "user-a", "https://x.com/h", ["document.deleted"], secret="my-secret"
        )
        assert wh["secret"] == "my-secret"

    def test_create_unsupported_event_raises(self, redis_client):
        with pytest.raises(ValueError):
            webhooks.create_webhook(redis_client, "user-a", "https://x.com/h", ["not.a.real.event"])

    def test_list_and_delete(self, redis_client):
        wh = webhooks.create_webhook(redis_client, "user-a", "https://x.com/h", ["document.ingested"])
        assert len(webhooks.list_webhooks(redis_client, "user-a")) == 1
        assert webhooks.delete_webhook(redis_client, "user-a", wh["webhook_id"]) is True
        assert webhooks.list_webhooks(redis_client, "user-a") == []

    def test_delete_unknown_returns_false(self, redis_client):
        assert webhooks.delete_webhook(redis_client, "user-a", "nope") is False


class TestSignature:
    def test_sign_is_verifiable_hmac(self):
        body = b'{"event":"ping"}'
        sig = webhooks._sign("secret", body)
        expected = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        assert sig == expected


class TestDelivery:
    def test_dispatch_only_hits_subscribed_active_webhooks(self, redis_client, monkeypatch):
        posted = []

        def fake_post(url, data=None, headers=None, timeout=None):
            posted.append((url, data, headers))
            return _FakeResponse(200)

        monkeypatch.setattr(webhooks.requests, "post", fake_post)

        # Subscribed to ingested only.
        webhooks.create_webhook(redis_client, "user-a", "https://a.com/h", ["document.ingested"])
        # Subscribed to deleted only -- must NOT fire on ingested.
        webhooks.create_webhook(redis_client, "user-a", "https://b.com/h", ["document.deleted"])

        webhooks.dispatch_event(redis_client, "user-a", "document.ingested", {"file_name": "x.pdf"})

        assert len(posted) == 1
        assert posted[0][0] == "https://a.com/h"

    def test_signature_header_matches_body(self, redis_client, monkeypatch):
        captured = {}

        def fake_post(url, data=None, headers=None, timeout=None):
            captured["data"] = data
            captured["headers"] = headers
            return _FakeResponse(200)

        monkeypatch.setattr(webhooks.requests, "post", fake_post)

        wh = webhooks.create_webhook(
            redis_client, "user-a", "https://a.com/h", ["document.ingested"], secret="s3cr3t"
        )
        webhooks.dispatch_event(redis_client, "user-a", "document.ingested", {"file_name": "x.pdf"})

        expected_sig = "sha256=" + hmac.new(b"s3cr3t", captured["data"], hashlib.sha256).hexdigest()
        assert captured["headers"]["X-Vaultly-Signature"] == expected_sig
        assert captured["headers"]["X-Vaultly-Event"] == "document.ingested"
        # Body is the metadata payload, not document content.
        body = json.loads(captured["data"])
        assert body["event"] == "document.ingested"
        assert body["data"] == {"file_name": "x.pdf"}

    def test_retry_then_success_updates_stats(self, redis_client, monkeypatch):
        calls = {"n": 0}

        def flaky_post(url, data=None, headers=None, timeout=None):
            calls["n"] += 1
            return _FakeResponse(500 if calls["n"] == 1 else 200)

        monkeypatch.setattr(webhooks.requests, "post", flaky_post)
        monkeypatch.setattr(webhooks.time, "sleep", lambda *_a, **_k: None)

        wh = webhooks.create_webhook(redis_client, "user-a", "https://a.com/h", ["document.ingested"])
        webhooks.dispatch_event(redis_client, "user-a", "document.ingested", {"file_name": "x.pdf"})

        assert calls["n"] == 2
        updated = webhooks.get_webhook(redis_client, "user-a", wh["webhook_id"])
        assert updated["last_status"] == "200"
        assert updated["failure_count"] == 0

    def test_all_attempts_fail_increments_failure_count_without_raising(self, redis_client, monkeypatch):
        monkeypatch.setattr(
            webhooks.requests, "post", lambda *a, **k: _FakeResponse(503)
        )
        monkeypatch.setattr(webhooks.time, "sleep", lambda *_a, **_k: None)

        wh = webhooks.create_webhook(redis_client, "user-a", "https://a.com/h", ["document.ingested"])
        # Must not raise.
        webhooks.dispatch_event(redis_client, "user-a", "document.ingested", {"file_name": "x.pdf"})

        updated = webhooks.get_webhook(redis_client, "user-a", wh["webhook_id"])
        assert updated["failure_count"] == 1
        assert updated["last_status"] == "503"

    def test_dispatch_does_not_cross_users(self, redis_client, monkeypatch):
        posted = []
        monkeypatch.setattr(
            webhooks.requests, "post",
            lambda url, **k: (posted.append(url), _FakeResponse(200))[1],
        )
        webhooks.create_webhook(redis_client, "user-b", "https://b.com/h", ["document.ingested"])
        webhooks.dispatch_event(redis_client, "user-a", "document.ingested", {"file_name": "x.pdf"})
        assert posted == []

    def test_deliver_test_event_ignores_subscriptions(self, redis_client, monkeypatch):
        posted = []
        monkeypatch.setattr(
            webhooks.requests, "post",
            lambda url, data=None, headers=None, timeout=None: (posted.append((url, headers)), _FakeResponse(200))[1],
        )
        wh = webhooks.create_webhook(redis_client, "user-a", "https://a.com/h", ["document.deleted"])
        assert webhooks.deliver_test_event(redis_client, "user-a", wh["webhook_id"]) is True
        assert len(posted) == 1
        assert posted[0][1]["X-Vaultly-Event"] == "ping"

    def test_deliver_test_event_unknown_webhook_returns_false(self, redis_client):
        assert webhooks.deliver_test_event(redis_client, "user-a", "nope") is False
