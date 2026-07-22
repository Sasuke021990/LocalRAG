"""HTTP-level tests for /chat/* conversation management routes."""

import pytest

from chat import store as chat_store


@pytest.fixture
def chat_client(redis_client):
    """TestClient mounting the real auth + chat routers (no heavy ML init)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth import routes as auth_routes
    from chat import routes as chat_routes

    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/auth")
    app.include_router(chat_routes.router, prefix="/chat")
    return TestClient(app)


def _signup(client, email="chatuser@example.com"):
    resp = client.post("/auth/signup", json={"email": email, "password": "longenough123"})
    assert resp.status_code == 200
    return resp.json()


class TestListConversations:
    def test_empty_list_for_new_user(self, chat_client):
        _signup(chat_client)
        assert chat_client.get("/chat/conversations").json()["conversations"] == []

    def test_lists_conversations_created_via_store(self, chat_client, redis_client):
        user = _signup(chat_client)
        chat_store.create_conversation(redis_client, user["user_id"], title="hello")
        body = chat_client.get("/chat/conversations").json()
        assert len(body["conversations"]) == 1
        assert body["conversations"][0]["title"] == "hello"

    def test_requires_auth(self, chat_client):
        assert chat_client.get("/chat/conversations").status_code == 401


class TestGetConversation:
    def test_get_returns_full_detail(self, chat_client, redis_client):
        user = _signup(chat_client)
        conv = chat_store.create_conversation(redis_client, user["user_id"], title="t")
        chat_store.append_message(redis_client, user["user_id"], conv["id"], "user", "hi")
        resp = chat_client.get(f"/chat/conversations/{conv['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "t"
        assert len(body["messages"]) == 1
        assert body["messages"][0]["content"] == "hi"

    def test_missing_conversation_404s(self, chat_client):
        _signup(chat_client)
        assert chat_client.get("/chat/conversations/no-such-id").status_code == 404

    def test_slimmed_sources_rehydrated_from_chunk_data(self, chat_client, redis_client):
        # Simulates main.py's _slim_sources: only file_name/pool/chunk_index/
        # score are persisted, no `content`. GET must re-attach it by reading
        # the still-durable chunk:* HASH (written by ingestion, unrelated to
        # chat storage) — proving the ~70%-smaller storage doesn't lose data.
        from retrieval import vector_index

        user = _signup(chat_client)
        uid = user["user_id"]
        vector_index.index_chunk(redis_client, uid, "General", "doc.txt", 0, "the real passage text", [0.0] * 4)

        conv = chat_store.create_conversation(redis_client, uid, title="t")
        chat_store.append_message(
            redis_client, uid, conv["id"], "assistant", "an answer",
            sources=[{"file_name": "doc.txt", "pool": "General", "chunk_index": 0, "score": 0.9}],
        )

        body = chat_client.get(f"/chat/conversations/{conv['id']}").json()
        assert body["messages"][0]["sources"][0]["content"] == "the real passage text"

    def test_hydration_falls_back_to_empty_when_chunk_gone(self, chat_client, redis_client):
        user = _signup(chat_client)
        conv = chat_store.create_conversation(redis_client, user["user_id"], title="t")
        chat_store.append_message(
            redis_client, user["user_id"], conv["id"], "assistant", "an answer",
            sources=[{"file_name": "deleted.txt", "pool": "General", "chunk_index": 0, "score": 0.5}],
        )
        body = chat_client.get(f"/chat/conversations/{conv['id']}").json()
        assert body["messages"][0]["sources"][0]["content"] == ""

    def test_already_hydrated_sources_left_alone(self, chat_client, redis_client):
        # Legacy data saved before the trimming change (full content already
        # present) — hydration must not overwrite or double-fetch it.
        user = _signup(chat_client)
        conv = chat_store.create_conversation(redis_client, user["user_id"], title="t")
        chat_store.append_message(
            redis_client, user["user_id"], conv["id"], "assistant", "an answer",
            sources=[{"file_name": "doc.txt", "pool": "General", "chunk_index": 0, "score": 0.5, "content": "already here"}],
        )
        body = chat_client.get(f"/chat/conversations/{conv['id']}").json()
        assert body["messages"][0]["sources"][0]["content"] == "already here"

    def test_cannot_get_another_users_conversation(self, chat_client, redis_client):
        _signup(chat_client, "owner@example.com")
        owner_id = chat_client.get("/auth/me").json()["user_id"]
        conv = chat_store.create_conversation(redis_client, owner_id, title="private")

        chat_client.post("/auth/logout")
        _signup(chat_client, "intruder@example.com")
        assert chat_client.get(f"/chat/conversations/{conv['id']}").status_code == 404


class TestRenameConversation:
    def test_rename_updates_title(self, chat_client, redis_client):
        user = _signup(chat_client)
        conv = chat_store.create_conversation(redis_client, user["user_id"], title="old")
        resp = chat_client.patch(f"/chat/conversations/{conv['id']}", json={"title": "new"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "new"
        assert chat_client.get(f"/chat/conversations/{conv['id']}").json()["title"] == "new"

    def test_rename_missing_404s(self, chat_client):
        _signup(chat_client)
        resp = chat_client.patch("/chat/conversations/no-such-id", json={"title": "x"})
        assert resp.status_code == 404


class TestDeleteConversation:
    def test_delete_removes_it(self, chat_client, redis_client):
        user = _signup(chat_client)
        conv = chat_store.create_conversation(redis_client, user["user_id"])
        assert chat_client.delete(f"/chat/conversations/{conv['id']}").status_code == 200
        assert chat_client.get(f"/chat/conversations/{conv['id']}").status_code == 404

    def test_delete_missing_404s(self, chat_client):
        _signup(chat_client)
        assert chat_client.delete("/chat/conversations/no-such-id").status_code == 404

    def test_cannot_delete_another_users_conversation(self, chat_client, redis_client):
        _signup(chat_client, "owner2@example.com")
        owner_id = chat_client.get("/auth/me").json()["user_id"]
        conv = chat_store.create_conversation(redis_client, owner_id)

        chat_client.post("/auth/logout")
        _signup(chat_client, "intruder2@example.com")
        assert chat_client.delete(f"/chat/conversations/{conv['id']}").status_code == 404
        # Still there for the real owner.
        assert chat_store.get_conversation(redis_client, owner_id, conv["id"]) is not None
