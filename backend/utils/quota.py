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

from fastapi import HTTPException

from auth import store

logger = logging.getLogger(__name__)


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
