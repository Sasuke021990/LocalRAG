"""
Per-user webhooks for Vaultly.

A user registers HTTP endpoint(s) that Vaultly POSTs to when a document
lifecycle event happens in their account. Payloads carry **metadata
only** (never document content), consistent with the product's
privacy principles, and are HMAC-SHA256 signed so the receiver can verify
authenticity.

Delivery is best-effort with a small inline retry loop (see
``dispatch_event``); a durable outbound queue is a documented scaling
follow-up, not needed at this stage.

Key schema
----------
webhook:<user_id>:<webhook_id>   HASH   {url, secret, events, created_at,
                                          is_active, last_status,
                                          last_delivered_at, failure_count}
webhooks:<user_id>               SET    -> {webhook_id, ...}
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from utils.config import config

logger = logging.getLogger(__name__)

SUPPORTED_EVENTS = {"document.ingested", "document.deleted", "document.ingest_failed"}


def _webhook_key(user_id: str, webhook_id: str) -> str:
    return f"webhook:{user_id}:{webhook_id}"


def _set_key(user_id: str) -> str:
    return f"webhooks:{user_id}"


def _sign(secret: str, body_bytes: bytes) -> str:
    """Compute the ``sha256=<hex>`` signature the receiver can verify."""
    digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _cast(raw: Dict[str, Any], webhook_id: str) -> Dict[str, Any]:
    return {
        "webhook_id": webhook_id,
        "url": raw.get("url", ""),
        "secret": raw.get("secret", ""),
        "events": [e for e in raw.get("events", "").split(",") if e],
        "is_active": bool(int(raw.get("is_active", 0))),
        "created_at": raw.get("created_at", ""),
        "last_status": raw.get("last_status", ""),
        "last_delivered_at": raw.get("last_delivered_at", ""),
        "failure_count": int(raw.get("failure_count", 0)),
    }


def create_webhook(
    redis_client, user_id: str, url: str, events: List[str], secret: Optional[str] = None
) -> Dict[str, Any]:
    """Register a webhook. Raises ValueError if any event is unsupported."""
    unsupported = set(events) - SUPPORTED_EVENTS
    if unsupported:
        raise ValueError(
            f"Unsupported event(s): {', '.join(sorted(unsupported))}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EVENTS))}"
        )

    webhook_id = uuid.uuid4().hex
    secret = secret or secrets.token_urlsafe(24)
    created_at = datetime.now().isoformat()

    redis_client.hset(
        _webhook_key(user_id, webhook_id),
        mapping={
            "url": url,
            "secret": secret,
            "events": ",".join(events),
            "created_at": created_at,
            "is_active": 1,
            "last_status": "",
            "last_delivered_at": "",
            "failure_count": 0,
        },
    )
    redis_client.sadd(_set_key(user_id), webhook_id)
    logger.info(f"Created webhook {webhook_id} for user {user_id} -> {url}")
    return _cast(redis_client.hgetall(_webhook_key(user_id, webhook_id)), webhook_id)


def get_webhook(redis_client, user_id: str, webhook_id: str) -> Optional[Dict[str, Any]]:
    raw = redis_client.hgetall(_webhook_key(user_id, webhook_id))
    if not raw:
        return None
    return _cast(raw, webhook_id)


def list_webhooks(redis_client, user_id: str) -> List[Dict[str, Any]]:
    webhook_ids = redis_client.smembers(_set_key(user_id))
    hooks = []
    for webhook_id in webhook_ids:
        raw = redis_client.hgetall(_webhook_key(user_id, webhook_id))
        if raw:
            hooks.append(_cast(raw, webhook_id))
    hooks.sort(key=lambda h: h["created_at"])
    return hooks


def delete_webhook(redis_client, user_id: str, webhook_id: str) -> bool:
    if not redis_client.exists(_webhook_key(user_id, webhook_id)):
        return False
    redis_client.delete(_webhook_key(user_id, webhook_id))
    redis_client.srem(_set_key(user_id), webhook_id)
    logger.info(f"Deleted webhook {webhook_id} for user {user_id}")
    return True


def _post_with_retries(url: str, body_bytes: bytes, headers: Dict[str, str]) -> tuple:
    """
    POST with up to ``WEBHOOK_MAX_RETRIES`` attempts. Returns
    ``(ok: bool, status: str)``. Never raises.
    """
    last_status = "no attempt"
    for attempt in range(1, config.WEBHOOK_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url, data=body_bytes, headers=headers, timeout=config.WEBHOOK_TIMEOUT_SECONDS
            )
            last_status = str(resp.status_code)
            if 200 <= resp.status_code < 300:
                return True, last_status
        except Exception as exc:
            last_status = f"error: {type(exc).__name__}"
        if attempt < config.WEBHOOK_MAX_RETRIES:
            time.sleep(min(2 ** (attempt - 1), 4))  # 1s, 2s, 4s cap
    return False, last_status


def _deliver_one(redis_client, user_id: str, webhook_id: str, raw: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Vaultly-Webhook/1.0",
        "X-Vaultly-Event": payload.get("event", ""),
        "X-Vaultly-Delivery": uuid.uuid4().hex,
        "X-Vaultly-Signature": _sign(raw.get("secret", ""), body_bytes),
    }
    ok, status = _post_with_retries(raw["url"], body_bytes, headers)

    key = _webhook_key(user_id, webhook_id)
    redis_client.hset(key, "last_status", status)
    redis_client.hset(key, "last_delivered_at", datetime.now().isoformat())
    if ok:
        redis_client.hset(key, "failure_count", 0)
    else:
        redis_client.hincrby(key, "failure_count", 1)
        logger.warning(f"Webhook {webhook_id} delivery failed for user {user_id}: {status}")
    return ok


def dispatch_event(redis_client, user_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """
    Deliver ``event_type`` to every active webhook of ``user_id`` that is
    subscribed to it. Synchronous and best-effort — safe to call from a
    background task; never raises.
    """
    payload = {
        "event": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }
    for webhook_id in redis_client.smembers(_set_key(user_id)):
        raw = redis_client.hgetall(_webhook_key(user_id, webhook_id))
        if not raw:
            continue
        if not int(raw.get("is_active", 0)):
            continue
        subscribed = {e for e in raw.get("events", "").split(",") if e}
        if event_type not in subscribed:
            continue
        _deliver_one(redis_client, user_id, webhook_id, raw, payload)


def deliver_test_event(redis_client, user_id: str, webhook_id: str) -> bool:
    """Send a ``ping`` event to a single webhook regardless of its subscriptions."""
    raw = redis_client.hgetall(_webhook_key(user_id, webhook_id))
    if not raw:
        return False
    payload = {
        "event": "ping",
        "timestamp": datetime.now().isoformat(),
        "data": {"message": "Vaultly test delivery"},
    }
    return _deliver_one(redis_client, user_id, webhook_id, raw, payload)
