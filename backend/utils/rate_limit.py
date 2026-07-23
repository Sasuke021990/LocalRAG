"""
Redis-backed fixed-window rate limiting for auth endpoints.

Why Redis (not an in-process counter): Vaultly's SaaS path runs multiple
stateless backend workers, so an in-memory limiter would let an attacker
get ``N × worker_count`` attempts. A shared Redis counter caps attempts
globally, across every worker.

The limiter **fails open**: if Redis is unreachable the request is allowed
(and a warning logged) rather than locking every user out during an
infrastructure hiccup — availability is chosen over strictness for a
best-effort throttle. The authoritative security controls (bcrypt, session
revocation, quotas) don't depend on it.

Fixed-window is used for simplicity; it permits a short burst across a
window boundary. That's an acceptable trade for auth throttling — tighten
to a sliding window later if abuse warrants it.
"""

import logging

from fastapi import HTTPException, Request

from auth.redis_client import redis_client
from utils.config import config

logger = logging.getLogger(__name__)

# scope -> (config attr for max, config attr for window). Read at call time so
# tests (and live env overrides) can adjust limits without re-importing.
_SCOPES = {
    "login": ("RATE_LIMIT_LOGIN_MAX", "RATE_LIMIT_LOGIN_WINDOW"),
    "signup": ("RATE_LIMIT_SIGNUP_MAX", "RATE_LIMIT_SIGNUP_WINDOW"),
    "password_reset": ("RATE_LIMIT_RESET_MAX", "RATE_LIMIT_RESET_WINDOW"),
}


def client_ip(request: Request) -> str:
    """
    Best-effort client IP. Trusts the left-most X-Forwarded-For hop only when
    ``TRUST_PROXY_HEADERS`` is set (i.e. a trusted proxy populates it) —
    otherwise uses the socket peer, since an unvalidated XFF is attacker-
    controlled and would let a client rotate the header to evade the limit.
    """
    if config.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(scope: str, identifier: str, limit: int, window_seconds: int) -> None:
    """
    Increment the counter for ``(scope, identifier)`` and raise 429 if it has
    exceeded ``limit`` within ``window_seconds``. No-op when rate limiting is
    disabled. Fails open on any Redis error.
    """
    if not config.RATE_LIMIT_ENABLED:
        return

    key = f"ratelimit:{scope}:{identifier}"
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, window_seconds)
    except Exception as exc:  # limiter must never take down the endpoint
        logger.warning("Rate limiter unavailable (%s) — allowing request", exc)
        return

    if count > limit:
        try:
            ttl = redis_client.ttl(key)
        except Exception:
            ttl = window_seconds
        retry_after = ttl if isinstance(ttl, int) and ttl > 0 else window_seconds
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down and try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit(scope: str):
    """
    FastAPI dependency factory: throttles ``scope`` per client IP. Limits are
    resolved from ``config`` at request time, so they stay overridable.

        @router.post("/login", dependencies=[Depends(rate_limit("login"))])
    """
    max_attr, window_attr = _SCOPES[scope]

    async def _dependency(request: Request) -> None:
        limit = getattr(config, max_attr)
        window = getattr(config, window_attr)
        check_rate_limit(scope, f"ip:{client_ip(request)}", limit, window)

    return _dependency
