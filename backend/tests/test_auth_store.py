"""Tests for auth.store (Redis-backed user store)."""

import pytest

from auth import store


class TestCreateAndLookup:
    def test_create_user_and_lookup_by_email_and_id(self, redis_client):
        user_id = store.create_user(redis_client, "alice@example.com", password_hash="hashed")

        by_id = store.get_user_by_id(redis_client, user_id)
        by_email = store.get_user_by_email(redis_client, "alice@example.com")

        assert by_id["email"] == "alice@example.com"
        assert by_id["password_hash"] == "hashed"
        assert by_id["token_version"] == 0
        assert by_id["storage_used_bytes"] == 0
        assert by_id["is_active"] == 1
        assert by_email["user_id"] == user_id

    def test_get_user_by_email_case_insensitive(self, redis_client):
        user_id = store.create_user(redis_client, "Alice@Example.com", password_hash="hashed")
        assert store.get_user_by_email(redis_client, "alice@example.com")["user_id"] == user_id

    def test_create_user_duplicate_email_raises(self, redis_client):
        store.create_user(redis_client, "alice@example.com", password_hash="hashed")
        with pytest.raises(ValueError):
            store.create_user(redis_client, "alice@example.com", password_hash="other")

    def test_get_user_by_id_missing_returns_none(self, redis_client):
        assert store.get_user_by_id(redis_client, "does-not-exist") is None

    def test_get_user_by_email_missing_returns_none(self, redis_client):
        assert store.get_user_by_email(redis_client, "nobody@example.com") is None


class TestGoogleLinking:
    def test_create_user_with_google_sub(self, redis_client):
        user_id = store.create_user(redis_client, "bob@example.com", google_sub="g-123")
        assert store.get_user_by_google_sub(redis_client, "g-123")["user_id"] == user_id

    def test_link_google_account_to_existing_user(self, redis_client):
        user_id = store.create_user(redis_client, "carol@example.com", password_hash="hashed")
        assert store.get_user_by_google_sub(redis_client, "g-456") is None

        store.link_google_account(redis_client, user_id, "g-456")

        linked = store.get_user_by_google_sub(redis_client, "g-456")
        assert linked["user_id"] == user_id
        assert linked["password_hash"] == "hashed"  # existing password preserved


class TestPasswordAndTokenVersion:
    def test_set_password_updates_hash(self, redis_client):
        user_id = store.create_user(redis_client, "dave@example.com", password_hash="old")
        store.set_password(redis_client, user_id, "new")
        assert store.get_user_by_id(redis_client, user_id)["password_hash"] == "new"

    def test_bump_token_version_increments(self, redis_client):
        user_id = store.create_user(redis_client, "eve@example.com", password_hash="hashed")
        store.bump_token_version(redis_client, user_id)
        store.bump_token_version(redis_client, user_id)
        assert store.get_user_by_id(redis_client, user_id)["token_version"] == 2


class TestPasswordResetToken:
    def test_password_reset_token_round_trip(self, redis_client):
        user_id = store.create_user(redis_client, "frank@example.com", password_hash="hashed")
        token = store.create_password_reset_token(redis_client, user_id)
        assert store.consume_password_reset_token(redis_client, token) == user_id

    def test_password_reset_token_consumed_once(self, redis_client):
        user_id = store.create_user(redis_client, "grace@example.com", password_hash="hashed")
        token = store.create_password_reset_token(redis_client, user_id)
        store.consume_password_reset_token(redis_client, token)
        assert store.consume_password_reset_token(redis_client, token) is None

    def test_consume_unknown_token_returns_none(self, redis_client):
        assert store.consume_password_reset_token(redis_client, "not-a-real-token") is None


class TestStorageQuotaFields:
    def test_default_quota_and_usage(self, redis_client):
        user_id = store.create_user(redis_client, "heidi@example.com", password_hash="hashed")
        assert store.get_storage_used(redis_client, user_id) == 0
        assert store.get_storage_quota(redis_client, user_id) > 0

    def test_increment_storage_used_floors_at_zero(self, redis_client):
        user_id = store.create_user(redis_client, "ivan@example.com", password_hash="hashed")
        store.increment_storage_used(redis_client, user_id, 500)
        assert store.get_storage_used(redis_client, user_id) == 500
        store.increment_storage_used(redis_client, user_id, -10_000)
        assert store.get_storage_used(redis_client, user_id) == 0

    def test_get_storage_used_missing_user_returns_zero(self, redis_client):
        assert store.get_storage_used(redis_client, "does-not-exist") == 0
