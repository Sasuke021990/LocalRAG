"""Tests for integrations.mcp_tokens (per-user API token store)."""

from integrations import mcp_tokens


class TestCreateAndResolve:
    def test_create_then_resolve_round_trip(self, redis_client):
        token, meta = mcp_tokens.create_token(redis_client, "user-a", "my-laptop")
        assert token.startswith("vlt_")
        assert meta["name"] == "my-laptop"
        assert mcp_tokens.resolve_token(redis_client, token) == "user-a"

    def test_prefix_is_first_12_chars_of_token(self, redis_client):
        token, meta = mcp_tokens.create_token(redis_client, "user-a", "t")
        assert meta["prefix"] == token[:12]

    def test_resolve_unknown_token_returns_none(self, redis_client):
        assert mcp_tokens.resolve_token(redis_client, "vlt_does-not-exist") is None

    def test_resolve_non_prefixed_token_returns_none(self, redis_client):
        # A JWT-shaped or garbage string must not be treated as a token.
        assert mcp_tokens.resolve_token(redis_client, "eyJhbGci.something.else") is None
        assert mcp_tokens.resolve_token(redis_client, "") is None

    def test_plaintext_is_never_stored(self, redis_client):
        token, _ = mcp_tokens.create_token(redis_client, "user-a", "t")
        # The raw token string must not appear as a value anywhere in Redis.
        for key in redis_client.keys("mcp_token*"):
            key_type = redis_client.type(key)
            if key_type == "string":
                assert redis_client.get(key) != token
            elif key_type == "hash":
                assert token not in redis_client.hgetall(key).values()

    def test_last_used_at_updates_on_resolve(self, redis_client):
        token, meta = mcp_tokens.create_token(redis_client, "user-a", "t")
        assert meta["last_used_at"] == ""
        mcp_tokens.resolve_token(redis_client, token)
        listed = mcp_tokens.list_tokens(redis_client, "user-a")
        assert listed[0]["last_used_at"] != ""


class TestListAndRevoke:
    def test_list_returns_metadata_without_hash_or_plaintext(self, redis_client):
        token, _ = mcp_tokens.create_token(redis_client, "user-a", "t")
        listed = mcp_tokens.list_tokens(redis_client, "user-a")
        assert len(listed) == 1
        entry = listed[0]
        assert "hash" not in entry
        assert "token" not in entry
        assert entry["prefix"] == token[:12]

    def test_list_multiple_sorted_by_created_at(self, redis_client):
        mcp_tokens.create_token(redis_client, "user-a", "first")
        mcp_tokens.create_token(redis_client, "user-a", "second")
        listed = mcp_tokens.list_tokens(redis_client, "user-a")
        assert [t["name"] for t in listed] == ["first", "second"]

    def test_revoke_then_resolve_returns_none(self, redis_client):
        token, meta = mcp_tokens.create_token(redis_client, "user-a", "t")
        assert mcp_tokens.revoke_token(redis_client, "user-a", meta["token_id"]) is True
        assert mcp_tokens.resolve_token(redis_client, token) is None
        assert mcp_tokens.list_tokens(redis_client, "user-a") == []

    def test_revoke_unknown_returns_false(self, redis_client):
        assert mcp_tokens.revoke_token(redis_client, "user-a", "nope") is False


class TestCrossUserIsolation:
    def test_token_resolves_only_to_its_owner(self, redis_client):
        token_a, _ = mcp_tokens.create_token(redis_client, "user-a", "a")
        token_b, _ = mcp_tokens.create_token(redis_client, "user-b", "b")
        assert mcp_tokens.resolve_token(redis_client, token_a) == "user-a"
        assert mcp_tokens.resolve_token(redis_client, token_b) == "user-b"

    def test_user_cannot_revoke_another_users_token(self, redis_client):
        _, meta_b = mcp_tokens.create_token(redis_client, "user-b", "b")
        # user-a tries to revoke user-b's token_id -> not found under user-a
        assert mcp_tokens.revoke_token(redis_client, "user-a", meta_b["token_id"]) is False
        # user-b's token still lists
        assert len(mcp_tokens.list_tokens(redis_client, "user-b")) == 1

    def test_user_a_does_not_see_user_b_tokens(self, redis_client):
        mcp_tokens.create_token(redis_client, "user-b", "b")
        assert mcp_tokens.list_tokens(redis_client, "user-a") == []
