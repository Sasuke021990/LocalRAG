"""
Redis-backed progress tracker for background ingestion tasks.

Each task's progress is a small JSON blob under ``upload_progress:<task_id>``
with a short TTL, so a client that never polls just lets the entry expire —
no cleanup job needed. Written by the ``POST /upload`` background task as it
moves through parse -> chunk -> embed -> store; read by ``GET
/progress/{task_id}`` (SSE) to report real phases instead of a fake timer.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_PREFIX = "upload_progress:"
_TTL_SECONDS = 600  # 10 minutes — comfortably longer than any single ingestion


def _key(task_id: str) -> str:
    return f"{_PREFIX}{task_id}"


def set_progress(
    redis_client, task_id: str, user_id: str, percent: int, message: str, status: str = "processing"
) -> None:
    """
    Write/overwrite one task's progress. ``status`` is one of
    ``processing`` | ``complete`` | ``failed``. Best-effort: a failure here
    should never take down the ingestion it's tracking.
    """
    try:
        redis_client.setex(
            _key(task_id), _TTL_SECONDS,
            json.dumps({"user_id": user_id, "percent": percent, "message": message, "status": status}),
        )
    except Exception as exc:
        logger.warning(f"Could not write progress for task {task_id}: {exc}")


def get_progress(redis_client, task_id: str) -> Optional[Dict[str, Any]]:
    """Return the task's current progress dict, or ``None`` if unknown/expired."""
    try:
        raw = redis_client.get(_key(task_id))
    except Exception as exc:
        logger.warning(f"Could not read progress for task {task_id}: {exc}")
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
