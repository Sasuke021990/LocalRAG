"""Tests for retrieval.semantic_cache.SemanticCache."""

import time

import numpy as np
import pytest

from retrieval.semantic_cache import SemanticCache, clear_user_cache
from tests.conftest import REDIS_HOST, REDIS_PORT

USER_A = "user-aaa"
USER_B = "user-bbb"


@pytest.fixture
def cache(redis_client):
    return SemanticCache(
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT,
        redis_db=0,
        default_ttl=60,
        similarity_threshold=0.92,
    )


class TestCosineSimilarity:
    def test_identical_vectors_similarity_one(self, cache):
        vec = [1.0, 0.0, 0.0]
        assert cache._cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors_similarity_zero(self, cache):
        assert cache._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_is_semantically_similar_respects_threshold(self, cache):
        a, b = [1.0, 0.0], [0.99, 0.01]
        assert cache._is_semantically_similar(a, b, threshold=0.9) is True
        assert cache._is_semantically_similar(a, [0.0, 1.0], threshold=0.9) is False

    def test_is_semantically_similar_empty_inputs(self, cache):
        assert cache._is_semantically_similar([], [1.0]) is False
        assert cache._is_semantically_similar(None, [1.0]) is False


class TestExactMatchCache:
    def test_miss_then_hit(self, cache):
        assert cache.get_cached_result(USER_A, "what is redis?") is None

        cache.set_cached_result(USER_A, "what is redis?", [{"answer": "an in-memory store", "sources": []}])

        result = cache.get_cached_result(USER_A, "what is redis?")
        assert result is not None
        assert result.results[0]["answer"] == "an in-memory store"

    def test_expired_entry_is_removed(self, cache):
        cache.set_cached_result(USER_A, "temp query", [{"answer": "x", "sources": []}], ttl=1)
        assert cache.get_cached_result(USER_A, "temp query") is not None
        time.sleep(1.1)
        assert cache.get_cached_result(USER_A, "temp query") is None

    def test_clear_cache(self, cache):
        cache.set_cached_result(USER_A, "q1", [{"answer": "a1", "sources": []}])
        cache.set_cached_result(USER_A, "q2", [{"answer": "a2", "sources": []}])
        assert cache.clear_cache(USER_A) is True
        assert cache.get_cached_result(USER_A, "q1") is None
        assert cache.get_cached_result(USER_A, "q2") is None

    def test_same_query_different_users_cached_separately(self, cache):
        cache.set_cached_result(USER_A, "shared question", [{"answer": "answer for A", "sources": []}])
        assert cache.get_cached_result(USER_B, "shared question") is None

        cache.set_cached_result(USER_B, "shared question", [{"answer": "answer for B", "sources": []}])
        assert cache.get_cached_result(USER_A, "shared question").results[0]["answer"] == "answer for A"
        assert cache.get_cached_result(USER_B, "shared question").results[0]["answer"] == "answer for B"

    def test_clear_cache_only_affects_owning_user(self, cache):
        cache.set_cached_result(USER_A, "q1", [{"answer": "a1", "sources": []}])
        cache.set_cached_result(USER_B, "q1", [{"answer": "b1", "sources": []}])

        cache.clear_cache(USER_A)

        assert cache.get_cached_result(USER_A, "q1") is None
        assert cache.get_cached_result(USER_B, "q1") is not None

    def test_clear_cache_also_clears_pool_scoped_entries(self, cache):
        """
        pipeline.stream_answer scopes pool-restricted queries under
        f"{user_id}::pool::{pool}" (see generation/pipeline.py) rather than
        the bare user_id. A plain clear_cache(user_id) -- called after a
        document upload/delete/move -- must still catch those, or a stale
        answer for pool-scoped questions (e.g. "key points" run against a
        specific pool) would survive the very document change meant to
        invalidate it.
        """
        pool_scope_docs = f"{USER_A}::pool::Docs"
        pool_scope_legal = f"{USER_A}::pool::Legal"
        cache.set_cached_result(USER_A, "unscoped q", [{"answer": "a0", "sources": []}])
        cache.set_cached_result(pool_scope_docs, "key points", [{"answer": "from Docs pool", "sources": []}])
        cache.set_cached_result(pool_scope_legal, "key points", [{"answer": "from Legal pool", "sources": []}])
        cache.set_cached_result(USER_B, "key points", [{"answer": "other user", "sources": []}])

        assert cache.clear_cache(USER_A) is True

        assert cache.get_cached_result(USER_A, "unscoped q") is None
        assert cache.get_cached_result(pool_scope_docs, "key points") is None
        assert cache.get_cached_result(pool_scope_legal, "key points") is None
        # A different user's cache (even for the same query text) is untouched.
        assert cache.get_cached_result(USER_B, "key points") is not None


class TestClearUserCacheFunction:
    """clear_user_cache is a module-level function (no SemanticCache/embedding
    model needed) -- used by routes that only need to invalidate, e.g.
    chat.routes.delete_conversation, without paying for a full cache instance."""

    def test_clears_all_of_one_users_entries_across_pool_scopes(self, cache, redis_client):
        cache.set_cached_result(USER_A, "q1", [{"answer": "a1", "sources": []}])
        cache.set_cached_result(f"{USER_A}::pool::Docs", "q2", [{"answer": "a2", "sources": []}])
        cache.set_cached_result(USER_B, "q1", [{"answer": "b1", "sources": []}])

        removed = clear_user_cache(redis_client, USER_A)

        assert removed >= 2
        assert cache.get_cached_result(USER_A, "q1") is None
        assert cache.get_cached_result(f"{USER_A}::pool::Docs", "q2") is None
        assert cache.get_cached_result(USER_B, "q1") is not None

    def test_returns_zero_when_nothing_to_clear(self, redis_client):
        assert clear_user_cache(redis_client, "user-with-nothing-cached") == 0


class TestSemanticSimilarityCache:
    def test_paraphrased_query_hits_cache(self, cache, monkeypatch):
        shared_vector = [1.0] + [0.0] * (384 - 1)

        def fake_embed(query):
            return shared_vector

        monkeypatch.setattr(cache, "_embed", fake_embed)

        cache.set_cached_result(USER_A, "how do I reset my password?", [{"answer": "go to settings", "sources": []}])

        result = cache.get_cached_result(USER_A, "how can I reset my password")
        assert result is not None
        assert result.results[0]["answer"] == "go to settings"

    def test_unrelated_query_does_not_hit_cache(self, cache):
        cache.set_cached_result(USER_A, "what is the capital of France?", [{"answer": "Paris", "sources": []}])

        # Hash-derived embeddings for unrelated strings are effectively
        # random unit vectors in 384 dims — expected cosine similarity ~0,
        # far below the 0.92 threshold.
        result = cache.get_cached_result(USER_A, "how does photosynthesis work in plants?")
        assert result is None

    def test_semantic_match_does_not_leak_across_users(self, cache, monkeypatch):
        shared_vector = [1.0] + [0.0] * (384 - 1)
        monkeypatch.setattr(cache, "_embed", lambda query: shared_vector)

        cache.set_cached_result(USER_A, "how do I reset my password?", [{"answer": "user A's answer", "sources": []}])

        # Same embedding, but a different user's paraphrase must not hit
        # user A's cached entry -- the candidate index is per-user.
        result = cache.get_cached_result(USER_B, "how can I reset my password")
        assert result is None

    def test_get_cache_stats_excludes_index_key(self, cache):
        cache.set_cached_result(USER_A, "q1", [{"answer": "a1", "sources": []}])
        stats = cache.get_cache_stats(USER_A)
        assert stats["cached_entries"] == 1
