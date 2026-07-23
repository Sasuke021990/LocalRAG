"""Tests for the auth rate limiter (utils.rate_limit)."""

import pytest


@pytest.fixture
def enable_rate_limiting(monkeypatch):
    """Re-enable the limiter (the suite-wide autouse fixture disables it) and
    tighten limits to small numbers so tests trip them in a few calls."""
    from utils.config import config
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "RATE_LIMIT_LOGIN_MAX", 3)
    monkeypatch.setattr(config, "RATE_LIMIT_LOGIN_WINDOW", 60)
    monkeypatch.setattr(config, "RATE_LIMIT_SIGNUP_MAX", 2)
    monkeypatch.setattr(config, "RATE_LIMIT_SIGNUP_WINDOW", 60)
    monkeypatch.setattr(config, "RATE_LIMIT_RESET_MAX", 2)
    monkeypatch.setattr(config, "RATE_LIMIT_RESET_WINDOW", 60)


def test_login_rate_limited_after_max_attempts(auth_client, enable_rate_limiting):
    # 3 allowed wrong-password attempts (401), the 4th is throttled (429).
    for _ in range(3):
        resp = auth_client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
        assert resp.status_code == 401
    blocked = auth_client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_signup_rate_limited_after_max_attempts(auth_client, enable_rate_limiting):
    # 2 signups allowed, the 3rd from the same IP is throttled.
    assert auth_client.post("/auth/signup", json={"username": "a", "email": "a@example.com", "password": "password123"}).status_code == 200
    assert auth_client.post("/auth/signup", json={"username": "b", "email": "b@example.com", "password": "password123"}).status_code == 200
    blocked = auth_client.post("/auth/signup", json={"username": "c", "email": "c@example.com", "password": "password123"})
    assert blocked.status_code == 429


def test_password_reset_rate_limited(auth_client, enable_rate_limiting):
    for _ in range(2):
        assert auth_client.post("/auth/password-reset/request", json={"email": "x@example.com"}).status_code == 200
    blocked = auth_client.post("/auth/password-reset/request", json={"email": "x@example.com"})
    assert blocked.status_code == 429


def test_disabled_limiter_never_blocks(auth_client, monkeypatch):
    # With the suite-wide disable fixture in effect, no throttling occurs.
    for _ in range(15):
        resp = auth_client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
        assert resp.status_code == 401
