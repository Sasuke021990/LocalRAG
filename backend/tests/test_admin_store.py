"""Tests for admin.store — metadata-only user administration."""

from admin import store as admin_store
from auth import passwords
from auth import store as auth_store
from chat import store as chat_store
from integrations import mcp_tokens, webhooks


def _make_user(redis_client, email):
    return auth_store.create_user(redis_client, email, password_hash=passwords.hash_password("longenough123"))


class TestListAndDetail:
    def test_list_users_returns_metadata_and_counts(self, redis_client):
        uid = _make_user(redis_client, "a@example.com")
        users = admin_store.list_users(redis_client)
        assert len(users) == 1
        u = users[0]
        assert u["email"] == "a@example.com"
        assert u["document_count"] == 0
        # No content/secret fields leak through.
        assert "password_hash" not in u

    def test_get_user_detail_includes_counts(self, redis_client):
        uid = _make_user(redis_client, "a@example.com")
        mcp_tokens.create_token(redis_client, uid, "t")
        webhooks.create_webhook(redis_client, uid, "https://x.com/h", ["document.ingested"])
        detail = admin_store.get_user_detail(redis_client, uid)
        assert detail["token_count"] == 1
        assert detail["webhook_count"] == 1

    def test_get_user_detail_missing_returns_none(self, redis_client):
        assert admin_store.get_user_detail(redis_client, "nope") is None


class TestSetters:
    def test_set_quota(self, redis_client):
        uid = _make_user(redis_client, "a@example.com")
        updated = admin_store.set_user_quota(redis_client, uid, 5000)
        assert updated["storage_quota_bytes"] == 5000
        assert auth_store.get_storage_quota(redis_client, uid) == 5000

    def test_set_active(self, redis_client):
        uid = _make_user(redis_client, "a@example.com")
        admin_store.set_user_active(redis_client, uid, False)
        assert auth_store.get_user_by_id(redis_client, uid)["is_active"] == 0

    def test_set_admin(self, redis_client):
        uid = _make_user(redis_client, "a@example.com")
        admin_store.set_user_admin(redis_client, uid, True)
        assert auth_store.get_user_by_id(redis_client, uid)["is_admin"] == 1

    def test_setters_on_missing_user_return_none(self, redis_client):
        assert admin_store.set_user_quota(redis_client, "nope", 1) is None
        assert admin_store.set_user_active(redis_client, "nope", True) is None
        assert admin_store.set_user_admin(redis_client, "nope", True) is None


class TestStats:
    def test_system_stats_aggregates(self, redis_client):
        a = _make_user(redis_client, "a@example.com")
        b = _make_user(redis_client, "b@example.com")
        admin_store.set_user_active(redis_client, b, False)
        admin_store.set_user_admin(redis_client, a, True)
        auth_store.increment_storage_used(redis_client, a, 1000)
        auth_store.increment_storage_used(redis_client, b, 500)

        stats = admin_store.system_stats(redis_client)
        assert stats["total_users"] == 2
        assert stats["active_users"] == 1
        assert stats["admin_users"] == 1
        assert stats["total_storage_used_bytes"] == 1500


class TestCascadeDelete:
    def test_delete_removes_every_namespace(self, redis_client, tmp_path):
        uid = _make_user(redis_client, "a@example.com")
        # Seed data across every namespace.
        redis_client.set(f"document:{uid}:General:x.pdf", '{"chunks":["secret text"]}')
        redis_client.hset(f"chunk:{uid}:General:x.pdf:0", mapping={"content": "secret text"})
        redis_client.set(f"semantic_cache:{uid}:abc", '{"results":[]}')
        token, _ = mcp_tokens.create_token(redis_client, uid, "t")
        webhooks.create_webhook(redis_client, uid, "https://x.com/h", ["document.ingested"])
        chat_store.append_message(redis_client, uid, chat_store.create_conversation(redis_client, uid)["id"], "user", "hi")
        (tmp_path / uid / "General").mkdir(parents=True)
        (tmp_path / uid / "General" / "x.json").write_text("{}")

        assert admin_store.delete_user_completely(redis_client, uid, data_dir=str(tmp_path)) is True

        # User + indices gone.
        assert auth_store.get_user_by_id(redis_client, uid) is None
        assert auth_store.get_user_by_email(redis_client, "a@example.com") is None
        assert auth_store.get_user_by_username(redis_client, "a") is None
        # Every owned key gone.
        assert redis_client.keys(f"document:{uid}:*") == []
        assert redis_client.keys(f"chunk:{uid}:*") == []
        assert redis_client.keys(f"semantic_cache:{uid}:*") == []
        assert redis_client.keys(f"webhook:{uid}:*") == []
        assert redis_client.keys(f"conversation:{uid}:*") == []
        assert redis_client.exists(f"conversation_index:{uid}") == 0
        assert redis_client.scard(f"mcp_tokens:{uid}") == 0
        # Token no longer resolves.
        assert mcp_tokens.resolve_token(redis_client, token) is None
        # Disk tree gone.
        assert not (tmp_path / uid).exists()

    def test_delete_then_resignup_with_same_email_succeeds(self, redis_client, tmp_path):
        """
        Regression test: delete_user_completely used to leave the derived
        username index (user_username_index:<local-part-of-email>) behind,
        so a re-signup with the same email (which re-derives the same
        username when none is given) would incorrectly 409 as "username
        already taken" even though the account was fully deleted.
        """
        uid = _make_user(redis_client, "reused@example.com")
        assert admin_store.delete_user_completely(redis_client, uid, data_dir=str(tmp_path)) is True

        new_uid = auth_store.create_user(
            redis_client, "reused@example.com", password_hash=passwords.hash_password("longenough123"),
        )
        assert new_uid != uid
        assert auth_store.get_user_by_email(redis_client, "reused@example.com")["user_id"] == new_uid

    def test_delete_missing_user_returns_false(self, redis_client):
        assert admin_store.delete_user_completely(redis_client, "nope", data_dir="/tmp") is False


class TestNoContentLeak:
    def test_no_admin_function_returns_document_content(self, redis_client):
        """The metadata-only rule: a stored document's text must never appear
        in any admin-store response."""
        uid = _make_user(redis_client, "a@example.com")
        secret = "TOP-SECRET-DOCUMENT-BODY-42"
        redis_client.set(f"document:{uid}:General:x.pdf", f'{{"chunks":["{secret}"]}}')
        redis_client.hset(f"chunk:{uid}:General:x.pdf:0", mapping={"content": secret})

        blobs = [
            admin_store.list_users(redis_client),
            admin_store.get_user_detail(redis_client, uid),
            admin_store.system_stats(redis_client),
        ]
        assert secret not in repr(blobs)
        # But the document is still counted (metadata, not content).
        assert admin_store.get_user_detail(redis_client, uid)["document_count"] == 1
