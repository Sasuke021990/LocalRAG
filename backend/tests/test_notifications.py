"""
Tests for push-notification token storage and Expo delivery (`requests`
mocked — no network).
"""

import json

import pytest

from notifications import push, store

USER_A = "push-user-a"
USER_B = "push-user-b"
TOKEN_A = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]"
TOKEN_B = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbbb]"


class TestTokenValidation:
    @pytest.mark.parametrize("token", [
        "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
        "ExpoPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
        "ExponentPushToken[abc-123_XYZ.def]",
    ])
    def test_valid_tokens_accepted(self, token):
        assert store.is_valid_token(token) is True

    @pytest.mark.parametrize("token", [
        "", "   ", "not-a-token", "ExponentPushToken[]",
        "ExponentPushToken[bad chars!]",
        "<script>alert(1)</script>",
        "ExponentPushToken[abc",
        "prefixExponentPushToken[abc]",
    ])
    def test_malformed_tokens_rejected(self, token):
        assert store.is_valid_token(token) is False


class TestRegistration:
    def test_register_and_read_back(self, redis_client):
        assert store.register_token(redis_client, USER_A, TOKEN_A) is True
        assert store.get_tokens(redis_client, USER_A) == [TOKEN_A]

    def test_register_is_idempotent(self, redis_client):
        store.register_token(redis_client, USER_A, TOKEN_A)
        store.register_token(redis_client, USER_A, TOKEN_A)
        assert store.get_tokens(redis_client, USER_A) == [TOKEN_A]

    def test_multiple_devices_per_user(self, redis_client):
        store.register_token(redis_client, USER_A, TOKEN_A)
        store.register_token(redis_client, USER_A, TOKEN_B)
        assert store.get_tokens(redis_client, USER_A) == sorted([TOKEN_A, TOKEN_B])

    def test_malformed_token_rejected_and_not_stored(self, redis_client):
        assert store.register_token(redis_client, USER_A, "junk") is False
        assert store.get_tokens(redis_client, USER_A) == []

    def test_whitespace_is_trimmed(self, redis_client):
        store.register_token(redis_client, USER_A, f"  {TOKEN_A}  ")
        assert store.get_tokens(redis_client, USER_A) == [TOKEN_A]

    def test_registering_another_users_token_reassigns_it(self, redis_client):
        """
        The shared-device case: someone logs out and a different account logs
        in on the same phone. Leaving the token attached to the first user
        would deliver *their* notifications to whoever is signed in now.
        """
        store.register_token(redis_client, USER_A, TOKEN_A)
        store.register_token(redis_client, USER_B, TOKEN_A)
        assert store.get_tokens(redis_client, USER_A) == []
        assert store.get_tokens(redis_client, USER_B) == [TOKEN_A]


class TestUnregistration:
    def test_unregister_removes_the_token(self, redis_client):
        store.register_token(redis_client, USER_A, TOKEN_A)
        store.unregister_token(redis_client, USER_A, TOKEN_A)
        assert store.get_tokens(redis_client, USER_A) == []

    def test_unregister_unknown_token_is_a_noop(self, redis_client):
        store.unregister_token(redis_client, USER_A, TOKEN_A)  # must not raise
        assert store.get_tokens(redis_client, USER_A) == []

    def test_stale_logout_does_not_unhook_a_reassigned_token(self, redis_client):
        # A leaves, B claims the device, then A's delayed logout arrives.
        # It must not detach the token B now owns.
        store.register_token(redis_client, USER_A, TOKEN_A)
        store.register_token(redis_client, USER_B, TOKEN_A)
        store.unregister_token(redis_client, USER_A, TOKEN_A)
        assert store.get_tokens(redis_client, USER_B) == [TOKEN_A]

    def test_clear_user_removes_every_token_and_owner_index(self, redis_client):
        store.register_token(redis_client, USER_A, TOKEN_A)
        store.register_token(redis_client, USER_A, TOKEN_B)
        store.clear_user(redis_client, USER_A)
        assert store.get_tokens(redis_client, USER_A) == []
        # The owner index must go too, or the token can never be re-registered
        # cleanly to a different account later.
        assert redis_client.get(f"push_token_owner:{TOKEN_A}") is None
        assert redis_client.get(f"push_token_owner:{TOKEN_B}") is None


class _FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
    def json(self):
        return self._body


class TestSend:
    def test_no_devices_sends_nothing(self, redis_client, monkeypatch):
        called = []
        monkeypatch.setattr(push.requests, "post", lambda *a, **k: called.append(1))
        assert push.send_to_user(redis_client, USER_A, "t", "b") == 0
        assert called == []

    def test_sends_to_every_registered_device(self, redis_client, monkeypatch):
        store.register_token(redis_client, USER_A, TOKEN_A)
        store.register_token(redis_client, USER_A, TOKEN_B)
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["messages"] = json
            return _FakeResponse({"data": [{"status": "ok"}, {"status": "ok"}]})

        monkeypatch.setattr(push.requests, "post", fake_post)
        assert push.send_to_user(redis_client, USER_A, "Title", "Body") == 2
        assert captured["url"] == push.EXPO_PUSH_URL
        assert {m["to"] for m in captured["messages"]} == {TOKEN_A, TOKEN_B}
        assert captured["messages"][0]["title"] == "Title"
        assert captured["messages"][0]["body"] == "Body"

    def test_data_payload_is_forwarded(self, redis_client, monkeypatch):
        store.register_token(redis_client, USER_A, TOKEN_A)
        captured = {}
        monkeypatch.setattr(
            push.requests, "post",
            lambda url, json=None, headers=None, timeout=None: (
                captured.update(messages=json), _FakeResponse({"data": [{"status": "ok"}]})
            )[1],
        )
        push.send_to_user(redis_client, USER_A, "t", "b", data={"type": "document.ingested"})
        assert captured["messages"][0]["data"] == {"type": "document.ingested"}

    def test_device_not_registered_prunes_the_token(self, redis_client, monkeypatch):
        store.register_token(redis_client, USER_A, TOKEN_A)
        monkeypatch.setattr(
            push.requests, "post",
            lambda *a, **k: _FakeResponse({"data": [
                {"status": "error", "message": "gone", "details": {"error": "DeviceNotRegistered"}},
            ]}),
        )
        assert push.send_to_user(redis_client, USER_A, "t", "b") == 0
        assert store.get_tokens(redis_client, USER_A) == []

    def test_other_ticket_errors_keep_the_token(self, redis_client, monkeypatch):
        # e.g. MessageRateExceeded — transient, the device is still valid.
        store.register_token(redis_client, USER_A, TOKEN_A)
        monkeypatch.setattr(
            push.requests, "post",
            lambda *a, **k: _FakeResponse({"data": [
                {"status": "error", "message": "slow down", "details": {"error": "MessageRateExceeded"}},
            ]}),
        )
        push.send_to_user(redis_client, USER_A, "t", "b")
        assert store.get_tokens(redis_client, USER_A) == [TOKEN_A]

    def test_network_failure_never_raises(self, redis_client, monkeypatch):
        store.register_token(redis_client, USER_A, TOKEN_A)

        def boom(*a, **k):
            raise ConnectionError("exp.host unreachable")

        monkeypatch.setattr(push.requests, "post", boom)
        # Must not raise — a failed notification can't break the upload that
        # triggered it.
        assert push.send_to_user(redis_client, USER_A, "t", "b") == 0
        assert store.get_tokens(redis_client, USER_A) == [TOKEN_A]

    def test_batch_level_rejection_is_handled(self, redis_client, monkeypatch):
        store.register_token(redis_client, USER_A, TOKEN_A)
        monkeypatch.setattr(
            push.requests, "post",
            lambda *a, **k: _FakeResponse({"errors": [{"code": "PUSH_TOO_MANY_EXPERIENCE_IDS"}]}),
        )
        assert push.send_to_user(redis_client, USER_A, "t", "b") == 0
        assert store.get_tokens(redis_client, USER_A) == [TOKEN_A]

    def test_mismatched_ticket_count_does_not_prune_wrong_tokens(self, redis_client, monkeypatch):
        # Tickets are positional; a short list must be ignored rather than
        # zipped against the wrong tokens (which could prune a live device).
        store.register_token(redis_client, USER_A, TOKEN_A)
        store.register_token(redis_client, USER_A, TOKEN_B)
        monkeypatch.setattr(
            push.requests, "post",
            lambda *a, **k: _FakeResponse({"data": [
                {"status": "error", "details": {"error": "DeviceNotRegistered"}},
            ]}),
        )
        push.send_to_user(redis_client, USER_A, "t", "b")
        assert store.get_tokens(redis_client, USER_A) == sorted([TOKEN_A, TOKEN_B])

    def test_batches_are_capped_at_the_expo_limit(self, redis_client, monkeypatch):
        for i in range(150):
            store.register_token(redis_client, USER_A, f"ExponentPushToken[{'t' * 10}{i:04d}]")
        batch_sizes = []

        def fake_post(url, json=None, headers=None, timeout=None):
            batch_sizes.append(len(json))
            return _FakeResponse({"data": [{"status": "ok"}] * len(json)})

        monkeypatch.setattr(push.requests, "post", fake_post)
        push.send_to_user(redis_client, USER_A, "t", "b")
        assert batch_sizes == [100, 50]
        assert all(size <= 100 for size in batch_sizes)
