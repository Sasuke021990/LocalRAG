"""Tests for retrieval.hybrid_search.HybridSearchEngine."""

import pytest

from retrieval import vector_index
from retrieval.hybrid_search import HybridSearchEngine, SearchResult
from tests.conftest import REDIS_HOST, REDIS_PORT

USER_A = "user-aaa"
USER_B = "user-bbb"


@pytest.fixture
def engine(redis_client, no_vector_index):
    return HybridSearchEngine(redis_host=REDIS_HOST, redis_port=REDIS_PORT, redis_db=0)


class TestBM25:
    def test_search_bm25_ranks_relevant_doc_first(self, engine):
        engine.setup_bm25_index(USER_A, [
            {"content": "The quick brown fox jumps over the lazy dog", "file_name": "a.txt"},
            {"content": "Redis is an in-memory data store used for caching", "file_name": "b.txt"},
            {"content": "Foxes are wild canines found across many continents", "file_name": "c.txt"},
        ])

        results = engine.search_bm25(USER_A, "fox", top_k=5)

        assert results, "expected at least one BM25 hit"
        assert results[0].metadata["file_name"] in {"a.txt", "c.txt"}
        assert all(r.source == "bm25" for r in results)

    def test_search_bm25_no_index_returns_empty(self, engine):
        assert engine.search_bm25(USER_A, "anything") == []

    def test_search_bm25_does_not_leak_across_users(self, engine):
        # BM25's IDF term needs more than one document to discriminate at
        # all -- with a single-document corpus even an exact keyword match
        # can score 0 (nothing to be "rarer" than) and get filtered out by
        # the `score > 0` check, independent of any leakage. Use a few
        # filler documents per user, matching the shape of
        # test_search_bm25_ranks_relevant_doc_first above, so this test
        # actually isolates the leakage behavior it's meant to check.
        engine.setup_bm25_index(USER_A, [
            {"content": "apple orchards produce fruit every autumn", "file_name": "a.txt"},
            {"content": "the stock market fluctuates based on economic indicators", "file_name": "a2.txt"},
            {"content": "mountain hiking requires proper equipment and preparation", "file_name": "a3.txt"},
        ])
        engine.setup_bm25_index(USER_B, [
            {"content": "banana plantations thrive in tropical climates", "file_name": "b.txt"},
            {"content": "quarterly earnings reports were released yesterday", "file_name": "b2.txt"},
            {"content": "the museum exhibit features ancient pottery", "file_name": "b3.txt"},
        ])

        assert engine.search_bm25(USER_A, "apple")
        assert engine.search_bm25(USER_A, "banana") == []
        assert engine.search_bm25(USER_B, "banana")
        assert engine.search_bm25(USER_B, "apple") == []


class TestFusion:
    def test_fuse_results_deduplicates_and_boosts_overlap(self, engine):
        shared = SearchResult(content="shared content", score=1.0, metadata={}, source="bm25")
        bm25_only = SearchResult(content="bm25 only content", score=0.9, metadata={}, source="bm25")
        vector_only = SearchResult(content="vector only content", score=0.8, metadata={}, source="vector")
        shared_from_vector = SearchResult(content="shared content", score=1.0, metadata={}, source="vector")

        fused = engine.fuse_results(
            bm25_results=[shared, bm25_only],
            redis_results=[shared_from_vector, vector_only],
            k=10,
        )

        contents = [r.content for r in fused]
        assert contents.count("shared content") == 1  # deduplicated
        # The chunk present in both result sets should outrank ones present in only one.
        assert fused[0].content == "shared content"
        assert len(fused) == 3

    def test_fuse_results_empty_inputs(self, engine):
        assert engine.fuse_results([], []) == []


class TestVectorSearch:
    def test_search_redis_no_documents_returns_empty(self, engine):
        assert engine.search_redis(USER_A, "anything") == []


class TestVectorSearchIntegration:
    """Requires a RediSearch build with VECTOR field support (redis-stack)."""

    def test_knn_search_ranks_closest_chunk_first(self, redis_client, redisearch_vector_available):
        if not redisearch_vector_available:
            pytest.skip("RediSearch VECTOR field support not available (needs redis-stack)")

        engine = HybridSearchEngine(redis_host=REDIS_HOST, redis_port=REDIS_PORT, redis_db=0)

        target_text = "the mitochondria is the powerhouse of the cell"
        target_embedding = engine.model.encode(target_text).tolist()
        distractor_embedding = [-x for x in target_embedding]

        vector_index.index_chunk(redis_client, USER_A, "Science", "bio.txt", 0, target_text, target_embedding)
        vector_index.index_chunk(redis_client, USER_A, "Science", "bio.txt", 1, "unrelated distractor text", distractor_embedding)
        # search_redis short-circuits on absence of document:<user_id>:* keys, so seed one.
        redis_client.set(f"document:{USER_A}:Science:bio.txt", "{}")

        results = engine.search_redis(USER_A, target_text, top_k=2)

        assert results
        assert results[0].content == target_text
        assert results[0].source == "vector"
        assert results[0].score > results[-1].score

    def test_search_redis_does_not_leak_across_users(self, redis_client, redisearch_vector_available):
        if not redisearch_vector_available:
            pytest.skip("RediSearch VECTOR field support not available (needs redis-stack)")

        engine = HybridSearchEngine(redis_host=REDIS_HOST, redis_port=REDIS_PORT, redis_db=0)

        text = "a passage about quarterly infrastructure costs"
        embedding = engine.model.encode(text).tolist()

        vector_index.index_chunk(redis_client, USER_A, "General", "mine.txt", 0, "user A's passage", embedding)
        vector_index.index_chunk(redis_client, USER_B, "General", "theirs.txt", 0, "user B's passage", embedding)
        redis_client.set(f"document:{USER_A}:General:mine.txt", "{}")

        results = engine.search_redis(USER_A, text, top_k=10)

        assert len(results) == 1
        assert results[0].content == "user A's passage"
