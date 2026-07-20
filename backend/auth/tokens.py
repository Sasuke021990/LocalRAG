"""Session JWT creation/verification for Vaultly accounts."""

from datetime import datetime, timedelta, timezone

import jwt

from utils.config import config

SESSION_COOKIE_NAME = "vaultly_session"


def create_session_token(user_id: str, token_version: int) -> str:
    payload = {
        "sub": user_id,
        "tv": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=config.SESSION_COOKIE_MAX_AGE_SECONDS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_session_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError (or a subclass, e.g. ExpiredSignatureError) on failure."""
    return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
