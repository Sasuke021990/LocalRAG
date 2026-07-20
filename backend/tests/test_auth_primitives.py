"""Tests for auth.passwords and auth.tokens (pure functions, no Redis needed)."""

import time

import jwt
import pytest

from auth import passwords, tokens


class TestPasswords:
    def test_hash_and_verify_round_trip(self):
        hashed = passwords.hash_password("correct-horse-battery-staple")
        assert passwords.verify_password("correct-horse-battery-staple", hashed)

    def test_verify_wrong_password_fails(self):
        hashed = passwords.hash_password("correct-horse-battery-staple")
        assert not passwords.verify_password("wrong-password", hashed)

    def test_hash_is_not_plaintext(self):
        assert passwords.hash_password("secret") != "secret"

    def test_verify_against_empty_hash_returns_false(self):
        assert not passwords.verify_password("anything", "")

    def test_verify_against_malformed_hash_returns_false(self):
        assert not passwords.verify_password("anything", "not-a-real-bcrypt-hash")


class TestTokens:
    def test_create_and_decode_round_trip(self):
        token = tokens.create_session_token("user-123", token_version=2)
        payload = tokens.decode_session_token(token)
        assert payload["sub"] == "user-123"
        assert payload["tv"] == 2

    def test_decode_invalid_token_raises(self):
        with pytest.raises(jwt.InvalidTokenError):
            tokens.decode_session_token("not-a-real-token")

    def test_decode_expired_token_raises(self, monkeypatch):
        from utils.config import config

        monkeypatch.setattr(config, "SESSION_COOKIE_MAX_AGE_SECONDS", -1)
        token = tokens.create_session_token("user-123", token_version=0)
        with pytest.raises(jwt.ExpiredSignatureError):
            tokens.decode_session_token(token)
