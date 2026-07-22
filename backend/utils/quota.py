"""
Per-user storage quota checks and accounting.

Quota is tracked incrementally on the user:<user_id> Redis HASH (see
auth.store), not recomputed by scanning keys on every request. The
tracked size is the JSON backup file's byte size -- see
ingestion.pipeline._save_json_backup's docstring for why that's an
accurate proxy without summing multiple overlapping representations of
the same content.
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from auth import store
from billing import plans as billing_plans
from billing import store as billing_store
from utils.config import config

logger = logging.getLogger(__name__)


def _is_admin(redis_client, user_id: str) -> bool:
    """
    True if the user operates the platform — either their stored ``is_admin``
    flag is set, or their email matches ``ADMIN_EMAIL``. Mirrors
    ``auth.routes._is_effective_admin`` so admin status is judged the same way
    everywhere.
    """
    user = store.get_user_by_id(redis_client, user_id)
    if not user:
        return False
    if user.get("is_admin"):
        return True
    return bool(config.ADMIN_EMAIL) and user.get("email", "").lower() == config.ADMIN_EMAIL.lower()

# AI-question quota keys expire 2 days out — comfortably past the daily
# rollover, so old days clean themselves up without a cron.
_AI_QUOTA_TTL_SECONDS = 60 * 60 * 48


def _ai_quota_key(user_id: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"ai_quota:{user_id}:{day}"


def get_ai_questions_used_today(redis_client, user_id: str) -> int:
    value = redis_client.get(_ai_quota_key(user_id))
    return int(value) if value else 0


def ai_questions_limit(redis_client, user_id: str) -> int:
    """This user's per-day AI-question allowance, from their current plan."""
    plan = billing_store.get_plan(redis_client, user_id)
    return billing_plans.ai_questions_per_day_for(plan)


def check_ai_question_allowed(redis_client, user_id: str) -> None:
    """
    Raise HTTPException(429) if the user has hit today's AI-question limit.
    Admin/operator accounts are exempt — they run the platform and must not be
    throttled by a consumer plan quota.
    """
    if _is_admin(redis_client, user_id):
        return
    limit = ai_questions_limit(redis_client, user_id)
    used = get_ai_questions_used_today(redis_client, user_id)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily AI question limit reached ({limit}/day on your current plan). "
                "Upgrade for a higher limit, or try again tomorrow."
            ),
        )


def record_ai_question(redis_client, user_id: str) -> int:
    """Count one AI question against today's quota. Returns the new daily total."""
    key = _ai_quota_key(user_id)
    new_total = redis_client.incr(key)
    if new_total == 1:
        redis_client.expire(key, _AI_QUOTA_TTL_SECONDS)
    return new_total


def check_upload_allowed(redis_client, user_id: str, upload_size_bytes: int) -> None:
    """
    Cheap pre-check using the raw upload size as an upper-bound heuristic.
    Raises HTTPException(413) if this upload would push the user over
    quota. Does not account for embedding/index overhead -- see
    record_ingested_document for the authoritative post-hoc check.
    """
    used = store.get_storage_used(redis_client, user_id)
    quota = store.get_storage_quota(redis_client, user_id)
    if used + upload_size_bytes > quota:
        raise HTTPException(
            status_code=413,
            detail=f"Storage quota exceeded: {used}/{quota} bytes used, upload is {upload_size_bytes} bytes",
        )


def record_ingested_document(redis_client, user_id: str, stored_bytes: int) -> None:
    """Increment storage_used_bytes by the ingested document's actual stored size."""
    store.increment_storage_used(redis_client, user_id, stored_bytes)


def record_deleted_document(redis_client, user_id: str, stored_bytes: int) -> None:
    """Decrement storage_used_bytes by a deleted document's stored size."""
    store.increment_storage_used(redis_client, user_id, -stored_bytes)


def is_over_quota(redis_client, user_id: str) -> bool:
    return store.get_storage_used(redis_client, user_id) > store.get_storage_quota(redis_client, user_id)
