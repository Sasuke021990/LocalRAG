"""Tests for chat.store — Redis-backed conversation storage."""

from chat import store as chat_store


class TestCreateAndGet:
    def test_create_returns_populated_conversation(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user, pool="Finance", title="My chat")
        assert conv["id"]
        assert conv["user_id"] == test_user
        assert conv["pool"] == "Finance"
        assert conv["title"] == "My chat"
        assert conv["messages"] == []
        assert conv["created_at"] == conv["updated_at"]

    def test_default_title_when_blank(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user, title="   ")
        assert conv["title"] == "New chat"

    def test_get_roundtrips(self, redis_client, test_user):
        created = chat_store.create_conversation(redis_client, test_user)
        fetched = chat_store.get_conversation(redis_client, test_user, created["id"])
        assert fetched == created

    def test_get_missing_returns_none(self, redis_client, test_user):
        assert chat_store.get_conversation(redis_client, test_user, "no-such-id") is None

    def test_get_scoped_to_owning_user(self, redis_client, test_user, second_test_user):
        conv = chat_store.create_conversation(redis_client, test_user)
        assert chat_store.get_conversation(redis_client, second_test_user, conv["id"]) is None


class TestAppendMessage:
    def test_append_adds_message_and_touches_updated_at(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user)
        updated = chat_store.append_message(redis_client, test_user, conv["id"], "user", "hello")
        assert len(updated["messages"]) == 1
        assert updated["messages"][0]["role"] == "user"
        assert updated["messages"][0]["content"] == "hello"
        assert "created_at" in updated["messages"][0]
        assert updated["updated_at"] >= conv["updated_at"]

    def test_append_assistant_carries_extra_fields(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user)
        updated = chat_store.append_message(
            redis_client, test_user, conv["id"], "assistant", "the answer",
            reasoning="because", sources=[{"file_name": "a.txt"}], refused=False,
        )
        msg = updated["messages"][-1]
        assert msg["reasoning"] == "because"
        assert msg["sources"] == [{"file_name": "a.txt"}]
        assert msg["refused"] is False

    def test_append_with_pool_updates_conversation_pool(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user, pool="")
        updated = chat_store.append_message(redis_client, test_user, conv["id"], "assistant", "x", pool="HR")
        assert updated["pool"] == "HR"

    def test_append_without_pool_kwarg_leaves_pool_unchanged(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user, pool="Finance")
        updated = chat_store.append_message(redis_client, test_user, conv["id"], "user", "x")
        assert updated["pool"] == "Finance"

    def test_append_to_missing_conversation_returns_none(self, redis_client, test_user):
        assert chat_store.append_message(redis_client, test_user, "no-such-id", "user", "hi") is None

    def test_messages_persist_in_order(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user)
        chat_store.append_message(redis_client, test_user, conv["id"], "user", "q1")
        chat_store.append_message(redis_client, test_user, conv["id"], "assistant", "a1")
        chat_store.append_message(redis_client, test_user, conv["id"], "user", "q2")
        fetched = chat_store.get_conversation(redis_client, test_user, conv["id"])
        assert [m["content"] for m in fetched["messages"]] == ["q1", "a1", "q2"]


class TestListConversations:
    def test_empty_for_new_user(self, redis_client, test_user):
        assert chat_store.list_conversations(redis_client, test_user) == []

    def test_newest_first(self, redis_client, test_user):
        first = chat_store.create_conversation(redis_client, test_user, title="first")
        second = chat_store.create_conversation(redis_client, test_user, title="second")
        listed = chat_store.list_conversations(redis_client, test_user)
        assert [c["id"] for c in listed] == [second["id"], first["id"]]

    def test_appending_bumps_to_top(self, redis_client, test_user):
        first = chat_store.create_conversation(redis_client, test_user, title="first")
        second = chat_store.create_conversation(redis_client, test_user, title="second")
        chat_store.append_message(redis_client, test_user, first["id"], "user", "revive me")
        listed = chat_store.list_conversations(redis_client, test_user)
        assert listed[0]["id"] == first["id"]
        assert listed[1]["id"] == second["id"]

    def test_summary_shape(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user, pool="Finance", title="t")
        chat_store.append_message(redis_client, test_user, conv["id"], "user", "a question here")
        summary = chat_store.list_conversations(redis_client, test_user)[0]
        assert summary["title"] == "t"
        assert summary["pool"] == "Finance"
        assert summary["message_count"] == 1
        assert summary["preview"] == "a question here"
        assert "messages" not in summary

    def test_scoped_per_user(self, redis_client, test_user, second_test_user):
        chat_store.create_conversation(redis_client, test_user, title="mine")
        chat_store.create_conversation(redis_client, second_test_user, title="theirs")
        assert [c["title"] for c in chat_store.list_conversations(redis_client, test_user)] == ["mine"]
        assert [c["title"] for c in chat_store.list_conversations(redis_client, second_test_user)] == ["theirs"]

    def test_self_heals_stale_index_entry(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user)
        # Simulate a dangling index entry (conversation blob deleted directly,
        # bypassing delete_conversation) — listing must not crash or return it.
        redis_client.delete(f"conversation:{test_user}:{conv['id']}")
        assert chat_store.list_conversations(redis_client, test_user) == []
        assert redis_client.zscore(f"conversation_index:{test_user}", conv["id"]) is None


class TestRenameAndDelete:
    def test_rename_updates_title(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user, title="old")
        renamed = chat_store.rename_conversation(redis_client, test_user, conv["id"], "new")
        assert renamed["title"] == "new"
        assert chat_store.get_conversation(redis_client, test_user, conv["id"])["title"] == "new"

    def test_rename_blank_falls_back_to_untitled(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user, title="old")
        renamed = chat_store.rename_conversation(redis_client, test_user, conv["id"], "   ")
        assert renamed["title"] == "Untitled"

    def test_rename_missing_returns_none(self, redis_client, test_user):
        assert chat_store.rename_conversation(redis_client, test_user, "no-such-id", "x") is None

    def test_delete_removes_conversation_and_index_entry(self, redis_client, test_user):
        conv = chat_store.create_conversation(redis_client, test_user)
        assert chat_store.delete_conversation(redis_client, test_user, conv["id"]) is True
        assert chat_store.get_conversation(redis_client, test_user, conv["id"]) is None
        assert chat_store.list_conversations(redis_client, test_user) == []

    def test_delete_missing_returns_false(self, redis_client, test_user):
        assert chat_store.delete_conversation(redis_client, test_user, "no-such-id") is False

    def test_delete_does_not_affect_other_users(self, redis_client, test_user, second_test_user):
        conv = chat_store.create_conversation(redis_client, second_test_user)
        assert chat_store.delete_conversation(redis_client, test_user, conv["id"]) is False
        assert chat_store.get_conversation(redis_client, second_test_user, conv["id"]) is not None


class TestEnforceConversationLimit:
    def test_noop_when_under_limit(self, redis_client, test_user):
        for i in range(3):
            chat_store.create_conversation(redis_client, test_user, title=f"c{i}")
        chat_store.enforce_conversation_limit(redis_client, test_user, limit=5)
        assert len(chat_store.list_conversations(redis_client, test_user)) == 3

    def test_evicts_oldest_when_at_limit(self, redis_client, test_user):
        ids = [chat_store.create_conversation(redis_client, test_user, title=f"c{i}")["id"] for i in range(3)]
        chat_store.enforce_conversation_limit(redis_client, test_user, limit=3)
        remaining = {c["id"] for c in chat_store.list_conversations(redis_client, test_user)}
        assert ids[0] not in remaining  # oldest (first created, never touched again) evicted
        assert ids[1] in remaining
        assert ids[2] in remaining
        assert len(remaining) == 2

    def test_recently_touched_conversation_survives(self, redis_client, test_user):
        first = chat_store.create_conversation(redis_client, test_user, title="first")
        second = chat_store.create_conversation(redis_client, test_user, title="second")
        # Touch "first" so it's now the most-recently-updated, not "second".
        chat_store.append_message(redis_client, test_user, first["id"], "user", "revive me")
        chat_store.enforce_conversation_limit(redis_client, test_user, limit=2)
        remaining = {c["id"] for c in chat_store.list_conversations(redis_client, test_user)}
        assert first["id"] in remaining
        assert second["id"] not in remaining

    def test_unlimited_when_limit_zero_or_negative(self, redis_client, test_user):
        for i in range(5):
            chat_store.create_conversation(redis_client, test_user, title=f"c{i}")
        chat_store.enforce_conversation_limit(redis_client, test_user, limit=0)
        chat_store.enforce_conversation_limit(redis_client, test_user, limit=-1)
        assert len(chat_store.list_conversations(redis_client, test_user)) == 5

    def test_scoped_per_user(self, redis_client, test_user, second_test_user):
        for i in range(3):
            chat_store.create_conversation(redis_client, test_user, title=f"mine{i}")
        chat_store.create_conversation(redis_client, second_test_user, title="theirs")
        chat_store.enforce_conversation_limit(redis_client, test_user, limit=3)
        assert len(chat_store.list_conversations(redis_client, second_test_user)) == 1
