"""
Tests for retrieval.vector_index.

Requires a RediSearch build with VECTOR field support (RediSearch >= 2.4,
bundled by redis-stack). Skips cleanly in environments without it (e.g. a
plain redis-server) — CI runs these against a redis-stack service
container.

All tests use the module's default EMBEDDING_DIM (384) consistently:
the index is created once per RediSearch VECTOR field with a fixed
dimension, so mixing dims across tests against the same index name would
be a self-inflicted footgun, not something the module needs to support.
"""

import pytest

from retrieval import vector_index
from tests.conftest import REDIS_HOST, REDIS_PORT

DIM = vector_index.EMBEDDING_DIM
USER_A = "user-aaa"
USER_B = "user-bbb"


def _unit_vector(hot_index: int) -> list:
    vec = [0.0] * DIM
    vec[hot_index] = 1.0
    return vec


@pytest.fixture(autouse=True)
def _ensure_index(redis_client, redisearch_vector_available):
    # Depending on redisearch_vector_available (rather than two independent
    # autouse fixtures) guarantees the skip is evaluated before ensure_index
    # runs -- pytest does not otherwise order same-scope autouse fixtures.
    if not redisearch_vector_available:
        pytest.skip("RediSearch VECTOR field support not available (needs redis-stack)")
    vector_index.ensure_index(redis_client)


def test_ensure_index_is_idempotent(redis_client):
    vector_index.ensure_index(redis_client)  # already created by the autouse fixture
    info = redis_client.ft(vector_index.INDEX_NAME).info()
    assert info is not None


def test_index_chunk_and_knn_search_orders_by_similarity(redis_client):
    target = _unit_vector(0)
    near = [0.0] * DIM
    near[0], near[1] = 0.9, 0.1
    far = _unit_vector(DIM - 1)

    vector_index.index_chunk(redis_client, USER_A, "General", "doc.txt", 0, "target chunk", target)
    vector_index.index_chunk(redis_client, USER_A, "General", "doc.txt", 1, "near chunk", near)
    vector_index.index_chunk(redis_client, USER_A, "General", "doc.txt", 2, "far chunk", far)

    results = vector_index.knn_search(redis_client, USER_A, target, top_k=3)

    assert [r["content"] for r in results][:2] == ["target chunk", "near chunk"]
    assert results[0]["score"] > results[1]["score"] > results[2]["score"]
    assert results[0]["file_name"] == "doc.txt"
    assert results[0]["category"] == "General"


def test_delete_chunks_removes_hashes(redis_client):
    vector_index.index_chunk(redis_client, USER_A, "General", "doc.txt", 0, "chunk 0", _unit_vector(0))
    vector_index.index_chunk(redis_client, USER_A, "General", "doc.txt", 1, "chunk 1", _unit_vector(1))

    vector_index.delete_chunks(redis_client, USER_A, "General", "doc.txt", chunk_count=2)

    assert redis_client.exists(vector_index.chunk_key(USER_A, "General", "doc.txt", 0)) == 0
    assert redis_client.exists(vector_index.chunk_key(USER_A, "General", "doc.txt", 1)) == 0


def test_knn_search_empty_index_returns_empty(redis_client):
    assert vector_index.knn_search(redis_client, USER_A, _unit_vector(0), top_k=5) == []


def test_knn_search_does_not_leak_across_users(redis_client):
    """
    The KNN pre-filter (@user_id:{<uid>}) must exclude another user's
    vectors entirely, not just rank them lower -- even when user B's
    chunk is a near-perfect match for user A's query.
    """
    shared_vector = _unit_vector(0)

    vector_index.index_chunk(redis_client, USER_A, "General", "mine.txt", 0, "user A's chunk", shared_vector)
    vector_index.index_chunk(redis_client, USER_B, "General", "theirs.txt", 0, "user B's chunk", shared_vector)

    results = vector_index.knn_search(redis_client, USER_A, shared_vector, top_k=10)

    assert len(results) == 1
    assert results[0]["content"] == "user A's chunk"
    assert results[0]["file_name"] == "mine.txt"
