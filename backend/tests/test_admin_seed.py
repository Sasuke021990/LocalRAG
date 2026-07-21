"""Tests for auth.store.ensure_default_admin (default admin seeding)."""

from auth import passwords, store


class TestEnsureDefaultAdmin:
    def test_creates_admin_when_missing(self, redis_client):
        user_id = store.ensure_default_admin(redis_client, "admin@example.com", "supersecret1")
        assert user_id is not None

        user = store.get_user_by_id(redis_client, user_id)
        assert user["email"] == "admin@example.com"
        assert user["is_admin"] == 1
        assert passwords.verify_password("supersecret1", user["password_hash"])

    def test_idempotent_second_call_returns_none(self, redis_client):
        first = store.ensure_default_admin(redis_client, "admin@example.com", "supersecret1")
        second = store.ensure_default_admin(redis_client, "admin@example.com", "different-pass")
        assert first is not None
        assert second is None

    def test_does_not_change_password_on_existing_account(self, redis_client):
        store.ensure_default_admin(redis_client, "admin@example.com", "originalpass1")
        store.ensure_default_admin(redis_client, "admin@example.com", "attacker-pass")
        user = store.get_user_by_email(redis_client, "admin@example.com")
        assert passwords.verify_password("originalpass1", user["password_hash"])
        assert not passwords.verify_password("attacker-pass", user["password_hash"])

    def test_promotes_existing_non_admin_user(self, redis_client):
        uid = store.create_user(redis_client, "existing@example.com", password_hash="hashed")
        assert store.get_user_by_id(redis_client, uid)["is_admin"] == 0

        result = store.ensure_default_admin(redis_client, "existing@example.com", "whatever1")
        assert result is None  # not newly created
        assert store.get_user_by_id(redis_client, uid)["is_admin"] == 1

    def test_no_email_is_noop(self, redis_client):
        assert store.ensure_default_admin(redis_client, "", "whatever1") is None

    def test_set_admin_toggles_flag(self, redis_client):
        uid = store.create_user(redis_client, "u@example.com", password_hash="hashed")
        store.set_admin(redis_client, uid, True)
        assert store.get_user_by_id(redis_client, uid)["is_admin"] == 1
        store.set_admin(redis_client, uid, False)
        assert store.get_user_by_id(redis_client, uid)["is_admin"] == 0
