"""Tests for utils.system_settings and its wiring into signup/create_user."""

import pytest

from auth import store as auth_store
from utils import system_settings
from utils.config import config


class TestSettingsStore:
    def test_unset_returns_fallback(self, redis_client):
        assert system_settings.signups_enabled(redis_client) is True
        assert system_settings.get_default_quota(redis_client) == config.DEFAULT_STORAGE_QUOTA_BYTES

    def test_set_and_get_bool(self, redis_client):
        system_settings.set_setting(redis_client, "signups_enabled", False)
        assert system_settings.signups_enabled(redis_client) is False
        system_settings.set_setting(redis_client, "signups_enabled", "true")
        assert system_settings.signups_enabled(redis_client) is True

    def test_set_and_get_int(self, redis_client):
        system_settings.set_setting(redis_client, "default_storage_quota_bytes", 2048)
        assert system_settings.get_default_quota(redis_client) == 2048

    def test_unknown_setting_raises(self, redis_client):
        with pytest.raises(ValueError):
            system_settings.set_setting(redis_client, "not_a_setting", 1)
        with pytest.raises(ValueError):
            system_settings.get_setting(redis_client, "not_a_setting")

    def test_get_all_returns_effective_values(self, redis_client):
        system_settings.set_setting(redis_client, "default_storage_quota_bytes", 999)
        allv = system_settings.get_all(redis_client)
        assert allv["default_storage_quota_bytes"] == 999
        assert allv["signups_enabled"] is True


class TestCreateUserRespectsDefaultQuota:
    def test_new_user_inherits_configured_default_quota(self, redis_client):
        system_settings.set_setting(redis_client, "default_storage_quota_bytes", 12345)
        user_id = auth_store.create_user(redis_client, "a@example.com", password_hash="h")
        assert auth_store.get_storage_quota(redis_client, user_id) == 12345
