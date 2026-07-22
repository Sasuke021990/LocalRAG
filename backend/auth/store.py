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

from utils import system_settings
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


def create_user(
    redis_client, email: str, password_hash: str = "", google_sub: str = "", username: str = ""
) -> str:
    """
    Create a new user. Raises ValueError if the email is already registered.
    ``username`` falls back to the email's local part (before ``@``) when not
    given — e.g. for the Google OAuth path when Google didn't return a name,
    and for the default-admin seed.
    """
    if redis_client.exists(_email_index_key(email)):
        raise ValueError("email already registered")

    user_id = uuid.uuid4().hex
    redis_client.hset(
        _user_key(user_id),
        mapping={
            "username": (username or "").strip() or email.split("@")[0],
            "email": email,
            "password_hash": password_hash,
            "google_sub": google_sub,
            "created_at": datetime.now().isoformat(),
            "token_version": 0,
            "storage_quota_bytes": system_settings.get_default_quota(redis_client),
            "storage_used_bytes": 0,
            "plan": "free",
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


def is_effective_admin(user: Optional[Dict[str, Any]]) -> bool:
    """
    True if `user` (an already-fetched dict, e.g. from ``get_user_by_id``) is
    an admin/operator: either the stored ``is_admin`` flag is set, or their
    email matches the operator account (``ADMIN_EMAIL``). Single source of
    truth for "does this account get admin privileges" — used by the admin
    panel gate, the AI-question-quota exemption, and the conversation-cap
    exemption, so admin status is judged identically everywhere.
    """
    if not user:
        return False
    if user.get("is_admin"):
        return True
    return bool(config.ADMIN_EMAIL) and user.get("email", "").lower() == config.ADMIN_EMAIL.lower()


def is_effective_admin_by_id(redis_client, user_id: str) -> bool:
    """Convenience: fetch the user then delegate to ``is_effective_admin``."""
    return is_effective_admin(get_user_by_id(redis_client, user_id))


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


def set_admin(redis_client, user_id: str, is_admin: bool) -> None:
    redis_client.hset(_user_key(user_id), "is_admin", 1 if is_admin else 0)


def ensure_default_admin(redis_client, email: str, password: str) -> Optional[str]:
    """
    Seed a default admin account (create-if-missing) so there's an admin to
    log in as out of the box. Idempotent: if the email already exists, only
    ensures its ``is_admin`` flag is set (never touches the password). Returns
    the user_id if a new account was created, else ``None``.

    Import inline to avoid an auth.store → auth.passwords cycle at module load.
    """
    from auth import passwords

    if not email:
        return None

    existing = get_user_by_email(redis_client, email)
    if existing is not None:
        if not existing.get("is_admin"):
            set_admin(redis_client, existing["user_id"], True)
            logger.info(f"Promoted existing user {existing['user_id']} ({email}) to admin")
        return None

    user_id = create_user(redis_client, email, password_hash=passwords.hash_password(password))
    set_admin(redis_client, user_id, True)
    logger.info(f"Seeded default admin account: {email} (user_id={user_id})")
    return user_id
