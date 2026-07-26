"""
Outbound Expo push delivery.

Sends through Expo's push service (``exp.host``), which fans out to APNs
(iOS) and FCM (Android) so this backend never holds platform credentials
itself. Best-effort and never raises — a failed notification must not break
whatever produced it (an upload finishing, the daily insight job).

Dead tokens are pruned as a side effect: Expo replies ``DeviceNotRegistered``
for an uninstalled app or a rotated token, and that token is dropped rather
than retried forever (see ``store.remove_token_globally``).

Docs: https://docs.expo.dev/push-notifications/sending-notifications/
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from notifications import store

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

# Expo accepts at most 100 messages per request.
_MAX_BATCH = 100
_TIMEOUT_SECONDS = 15


def _post_batch(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """POST one batch, returning Expo's per-message tickets (empty on failure)."""
    resp = requests.post(
        EXPO_PUSH_URL,
        json=messages,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Expo compresses large responses; be explicit so `requests`
            # negotiates something it can transparently decode.
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    body = resp.json()
    # Success shape is {"data": [ticket, ...]}; a top-level {"errors": [...]}
    # means the whole batch was rejected (bad JSON, too many messages, ...).
    if isinstance(body, dict) and body.get("errors"):
        logger.error(f"Expo push rejected the batch: {body['errors']}")
        return []
    data = body.get("data") if isinstance(body, dict) else None
    return data if isinstance(data, list) else []


def _handle_tickets(redis_client, tokens: List[str], tickets: List[Dict[str, Any]]) -> None:
    """
    Prune tokens Expo reports as permanently undeliverable. Tickets come back
    positionally aligned with the messages sent, so a short/absent list is
    simply skipped rather than mismatched against the wrong tokens.
    """
    if len(tickets) != len(tokens):
        if tickets:
            logger.warning(
                f"Expo returned {len(tickets)} tickets for {len(tokens)} messages — skipping token pruning"
            )
        return
    for token, ticket in zip(tokens, tickets):
        if not isinstance(ticket, dict) or ticket.get("status") != "error":
            continue
        error_code = (ticket.get("details") or {}).get("error")
        message = ticket.get("message", "")
        if error_code == "DeviceNotRegistered":
            store.remove_token_globally(redis_client, token)
            logger.info("Pruned a push token Expo reported as DeviceNotRegistered")
        else:
            logger.warning(f"Expo push ticket error ({error_code}): {message}")


def send_to_user(
    redis_client,
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Push ``title``/``body`` to every device registered to this user.

    ``data`` is an arbitrary JSON payload the app reads to decide where to
    navigate when the notification is tapped — keep it to identifiers and
    metadata, never document content (same privacy rule as webhooks).

    Returns the number of messages accepted for delivery (0 if the user has
    no devices, or delivery failed). Never raises.
    """
    tokens = store.get_tokens(redis_client, user_id)
    if not tokens:
        return 0

    sent = 0
    for start in range(0, len(tokens), _MAX_BATCH):
        batch_tokens = tokens[start:start + _MAX_BATCH]
        messages = [
            {
                "to": token,
                "title": title,
                "body": body,
                "data": data or {},
                "sound": "default",
                # Android-only: routes to the channel the client created at
                # startup, which controls importance/heads-up behavior.
                "channelId": "default",
            }
            for token in batch_tokens
        ]
        try:
            tickets = _post_batch(messages)
        except Exception as exc:
            logger.error(f"Expo push delivery failed for user {user_id}: {exc}")
            continue
        _handle_tickets(redis_client, batch_tokens, tickets)
        sent += sum(
            1 for t in tickets if isinstance(t, dict) and t.get("status") == "ok"
        )

    logger.info(f"Push sent to user {user_id}: {sent}/{len(tokens)} device(s) accepted")
    return sent
