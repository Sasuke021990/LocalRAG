"""
Redis-backed user store for Vaultly accounts.

Key schema
----------
user:<user_id>                    HASH   email, password_hash, google_sub,
                                          created_at, token_version,
                                          storage_quota_bytes, storage_used_bytes,
                                          is_admin, is_active
user_email_index:<email lower>    STRING -> user_id
user_google_index:<google sub>    STRING -> user_id
password_reset:<token>            STRING -> user_id  (TTL 1 hour)
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from utils.config import config

logger = logging.getLogger(__name__)

PASSWORD_RESET_TTL_SECONDS = 3600


def _user_key(user_id: str) -> str:
    return f"user:{user_id}"


def _email_index_key(email: str) -> str:
    return f"user_email_index:{email.lower()}"


def _google_index_key(sub: str) -> str:
    return f"user_google_index:{sub}"


def _reset_token_key(token: str) -> str:
    return f"password_reset:{token}"


def create_user(redis_client, email: str, password_hash: str = "", google_sub: str = "") -> str:
    """Create a new user. Raises ValueError if the email is already registered."""
    if redis_client.exists(_email_index_key(email)):
        raise ValueError("email already registered")

    user_id = uuid.uuid4().hex
    redis_client.hset(
        _user_key(user_id),
        mapping={
            "email": email,
            "password_hash": password_hash,
            "google_sub": google_sub,
            "created_at": datetime.now().isoformat(),
            "token_version": 0,
            "storage_quota_bytes": config.DEFAULT_STORAGE_QUOTA_BYTES,
            "storage_used_bytes": 0,
            "is_admin": 0,
            "is_active": 1,
        },
    )
    redis_client.set(_email_index_key(email), user_id)
    if google_sub:
        redis_client.set(_google_index_key(google_sub), user_id)

    logger.info(f"Created user {user_id} ({email})")
    return user_id


def _cast_user_fields(raw: Dict[str, Any]) -> Dict[str, Any]:
    user = dict(raw)
    for int_field in ("token_version", "storage_quota_bytes", "storage_used_bytes", "is_admin", "is_active"):
        if int_field in user:
            user[int_field] = int(user[int_field])
    return user


def get_user_by_id(redis_client, user_id: str) -> Optional[Dict[str, Any]]:
    raw = redis_client.hgetall(_user_key(user_id))
    if not raw:
        return None
    user = _cast_user_fields(raw)
    user["user_id"] = user_id
    return user


def get_user_by_email(redis_client, email: str) -> Optional[Dict[str, Any]]:
    user_id = redis_client.get(_email_index_key(email))
    if not user_id:
        return None
    return get_user_by_id(redis_client, user_id)


def get_user_by_google_sub(redis_client, sub: str) -> Optional[Dict[str, Any]]:
    user_id = redis_client.get(_google_index_key(sub))
    if not user_id:
        return None
    return get_user_by_id(redis_client, user_id)


def link_google_account(redis_client, user_id: str, sub: str) -> None:
    redis_client.hset(_user_key(user_id), "google_sub", sub)
    redis_client.set(_google_index_key(sub), user_id)


def set_password(redis_client, user_id: str, password_hash: str) -> None:
    redis_client.hset(_user_key(user_id), "password_hash", password_hash)


def bump_token_version(redis_client, user_id: str) -> None:
    redis_client.hincrby(_user_key(user_id), "token_version", 1)


def create_password_reset_token(redis_client, user_id: str) -> str:
    token = uuid.uuid4().hex
    redis_client.setex(_reset_token_key(token), PASSWORD_RESET_TTL_SECONDS, user_id)
    return token


def consume_password_reset_token(redis_client, token: str) -> Optional[str]:
    key = _reset_token_key(token)
    user_id = redis_client.get(key)
    if not user_id:
        return None
    redis_client.delete(key)
    return user_id


def get_storage_used(redis_client, user_id: str) -> int:
    value = redis_client.hget(_user_key(user_id), "storage_used_bytes")
    return int(value) if value is not None else 0


def get_storage_quota(redis_client, user_id: str) -> int:
    value = redis_client.hget(_user_key(user_id), "storage_quota_bytes")
    return int(value) if value is not None else config.DEFAULT_STORAGE_QUOTA_BYTES


def increment_storage_used(redis_client, user_id: str, delta_bytes: int) -> None:
    key = _user_key(user_id)
    new_value = redis_client.hincrby(key, "storage_used_bytes", delta_bytes)
    if new_value < 0:
        redis_client.hset(key, "storage_used_bytes", 0)
