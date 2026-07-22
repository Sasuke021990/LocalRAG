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


class TestAiQuestionQuota:
    def test_new_user_on_free_has_ten_per_day(self, redis_client, user):
        # A new user defaults to the free plan (10 AI questions/day).
        assert quota.ai_questions_limit(redis_client, user) == 10
        assert quota.get_ai_questions_used_today(redis_client, user) == 0

    def test_record_increments_daily_count(self, redis_client, user):
        assert quota.record_ai_question(redis_client, user) == 1
        assert quota.record_ai_question(redis_client, user) == 2
        assert quota.get_ai_questions_used_today(redis_client, user) == 2

    def test_check_passes_under_limit(self, redis_client, user):
        for _ in range(9):
            quota.record_ai_question(redis_client, user)
        quota.check_ai_question_allowed(redis_client, user)  # 9 < 10, no raise

    def test_check_raises_429_at_limit(self, redis_client, user):
        for _ in range(10):
            quota.record_ai_question(redis_client, user)
        with pytest.raises(HTTPException) as exc_info:
            quota.check_ai_question_allowed(redis_client, user)
        assert exc_info.value.status_code == 429

    def test_limit_follows_plan(self, redis_client, user):
        from billing import store as billing_store
        billing_store.set_plan(redis_client, user, "pro")
        assert quota.ai_questions_limit(redis_client, user) == 25
        billing_store.set_plan(redis_client, user, "max")
        assert quota.ai_questions_limit(redis_client, user) == 30

    def test_admin_is_exempt_from_limit(self, redis_client, user):
        from auth import store as auth_store
        auth_store.set_admin(redis_client, user, True)
        for _ in range(50):  # far past any plan limit
            quota.record_ai_question(redis_client, user)
        quota.check_ai_question_allowed(redis_client, user)  # admin → no raise
