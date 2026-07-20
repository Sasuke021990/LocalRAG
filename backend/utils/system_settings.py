"""
Redis-backed runtime system settings for Vaultly.

Unlike env-var config (fixed at process start), these settings can be
changed at runtime by an admin via the admin API and take effect
immediately. Kept in ``utils`` (not ``admin``) so ``auth`` can read them
without an auth->admin import.

Stored as a single HASH ``system:settings``. Only keys in ``KNOWN`` are
accepted; each has a type and a fallback used when the key is unset.

Known settings
--------------
default_storage_quota_bytes : int   New signups inherit this quota.
                                    Falls back to config.DEFAULT_STORAGE_QUOTA_BYTES.
signups_enabled             : bool  When false, public signup is rejected.
                                    Falls back to True.
"""

from typing import Any, Dict

from utils.config import config

SETTINGS_KEY = "system:settings"

# name -> (python type, fallback value)
KNOWN: Dict[str, tuple] = {
    "default_storage_quota_bytes": (int, None),   # None -> resolved from config below
    "signups_enabled": (bool, True),
}


def _fallback(name: str) -> Any:
    if name == "default_storage_quota_bytes":
        return config.DEFAULT_STORAGE_QUOTA_BYTES
    return KNOWN[name][1]


def _coerce(name: str, raw: Any) -> Any:
    typ = KNOWN[name][0]
    if typ is bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if typ is int:
        return int(raw)
    return raw


def get_setting(redis_client, name: str) -> Any:
    """Return the effective (stored or fallback), correctly-typed value."""
    if name not in KNOWN:
        raise ValueError(f"unknown setting: {name}")
    raw = redis_client.hget(SETTINGS_KEY, name)
    if raw is None:
        return _fallback(name)
    return _coerce(name, raw)


def set_setting(redis_client, name: str, value: Any) -> Any:
    """Validate + persist a setting. Returns the coerced stored value."""
    if name not in KNOWN:
        raise ValueError(f"unknown setting: {name}")
    coerced = _coerce(name, value)
    # Booleans are stored as "1"/"0" so they round-trip cleanly.
    stored = "1" if coerced is True else "0" if coerced is False else str(coerced)
    redis_client.hset(SETTINGS_KEY, name, stored)
    return coerced


def get_all(redis_client) -> Dict[str, Any]:
    """All known settings with their effective values."""
    return {name: get_setting(redis_client, name) for name in KNOWN}


def get_default_quota(redis_client) -> int:
    return int(get_setting(redis_client, "default_storage_quota_bytes"))


def signups_enabled(redis_client) -> bool:
    return bool(get_setting(redis_client, "signups_enabled"))
