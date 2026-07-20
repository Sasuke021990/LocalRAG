"""Tests for utils.quota."""

import pytest
from fastapi import HTTPException

from auth import store
from utils import quota

USER_ID = "user-quota-test"


@pytest.fixture
def user(redis_client):
    return store.create_user(redis_client, "quota@example.com", password_hash="hashed")


class TestCheckUploadAllowed:
    def test_passes_under_quota(self, redis_client, user):
        # Default quota is 1 GiB; a tiny upload should pass without raising.
        quota.check_upload_allowed(redis_client, user, upload_size_bytes=1024)

    def test_raises_over_quota(self, redis_client, user):
        redis_client.hset(f"user:{user}", "storage_quota_bytes", 1000)
        with pytest.raises(HTTPException) as exc_info:
            quota.check_upload_allowed(redis_client, user, upload_size_bytes=2000)
        assert exc_info.value.status_code == 413

    def test_exactly_at_quota_passes(self, redis_client, user):
        redis_client.hset(f"user:{user}", "storage_quota_bytes", 1000)
        quota.check_upload_allowed(redis_client, user, upload_size_bytes=1000)

    def test_accounts_for_existing_usage(self, redis_client, user):
        redis_client.hset(f"user:{user}", "storage_quota_bytes", 1000)
        redis_client.hset(f"user:{user}", "storage_used_bytes", 900)
        with pytest.raises(HTTPException):
            quota.check_upload_allowed(redis_client, user, upload_size_bytes=200)


class TestRecordIngestedAndDeleted:
    def test_record_ingested_document_updates_used_bytes(self, redis_client, user):
        quota.record_ingested_document(redis_client, user, 500)
        assert store.get_storage_used(redis_client, user) == 500

    def test_record_deleted_document_updates_used_bytes(self, redis_client, user):
        quota.record_ingested_document(redis_client, user, 500)
        quota.record_deleted_document(redis_client, user, 500)
        assert store.get_storage_used(redis_client, user) == 0

    def test_record_deleted_document_floors_at_zero(self, redis_client, user):
        quota.record_deleted_document(redis_client, user, 500)
        assert store.get_storage_used(redis_client, user) == 0


class TestIsOverQuota:
    def test_false_under_quota(self, redis_client, user):
        assert quota.is_over_quota(redis_client, user) is False

    def test_true_after_exceeding(self, redis_client, user):
        redis_client.hset(f"user:{user}", "storage_quota_bytes", 1000)
        quota.record_ingested_document(redis_client, user, 1500)
        assert quota.is_over_quota(redis_client, user) is True
