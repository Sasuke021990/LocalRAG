"""Tests for retrieval.semantic_cache.SemanticCache."""

import time

import numpy as np
import pytest

from retrieval.semantic_cache import SemanticCache
from tests.conftest import REDIS_HOST, REDIS_PORT


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
        assert cache.get_cached_result("what is redis?") is None

        cache.set_cached_result("what is redis?", [{"answer": "an in-memory store", "sources": []}])

        result = cache.get_cached_result("what is redis?")
        assert result is not None
        assert result.results[0]["answer"] == "an in-memory store"

    def test_expired_entry_is_removed(self, cache):
        cache.set_cached_result("temp query", [{"answer": "x", "sources": []}], ttl=1)
        assert cache.get_cached_result("temp query") is not None
        time.sleep(1.1)
        assert cache.get_cached_result("temp query") is None

    def test_clear_cache(self, cache):
        cache.set_cached_result("q1", [{"answer": "a1", "sources": []}])
        cache.set_cached_result("q2", [{"answer": "a2", "sources": []}])
        assert cache.clear_cache() is True
        assert cache.get_cached_result("q1") is None
        assert cache.get_cached_result("q2") is None


class TestSemanticSimilarityCache:
    def test_paraphrased_query_hits_cache(self, cache, monkeypatch):
        shared_vector = [1.0] + [0.0] * (384 - 1)

        def fake_embed(query):
            return shared_vector

        monkeypatch.setattr(cache, "_embed", fake_embed)

        cache.set_cached_result("how do I reset my password?", [{"answer": "go to settings", "sources": []}])

        result = cache.get_cached_result("how can I reset my password")
        assert result is not None
        assert result.results[0]["answer"] == "go to settings"

    def test_unrelated_query_does_not_hit_cache(self, cache):
        cache.set_cached_result("what is the capital of France?", [{"answer": "Paris", "sources": []}])

        # Hash-derived embeddings for unrelated strings are effectively
        # random unit vectors in 384 dims — expected cosine similarity ~0,
        # far below the 0.92 threshold.
        result = cache.get_cached_result("how does photosynthesis work in plants?")
        assert result is None

    def test_get_cache_stats_excludes_index_key(self, cache):
        cache.set_cached_result("q1", [{"answer": "a1", "sources": []}])
        stats = cache.get_cache_stats()
        assert stats["cached_entries"] == 1
