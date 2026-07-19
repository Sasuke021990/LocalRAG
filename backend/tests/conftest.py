"""
Shared pytest fixtures for the backend test suite.

Design notes
------------
- Tests run against a real Redis instance (``REDIS_HOST``/``REDIS_PORT``,
  defaulting to localhost:6379) rather than ``fakeredis``, because
  ``fakeredis`` does not implement the RediSearch (``FT.*``) commands that
  ``retrieval.vector_index`` relies on. If no Redis is reachable, the whole
  session is skipped rather than failing noisily.
- Real vector-index/KNN behavior additionally requires a RediSearch build
  with VECTOR field support (RediSearch >= 2.4, bundled by ``redis-stack``
  and used in CI via a service container). Tests that need it are gated
  behind the ``redisearch_available`` fixture and skip cleanly without it,
  e.g. in a plain-Redis local dev environment.
- The real ``sentence-transformers`` models are downloaded from HuggingFace
  Hub on first use, which is slow and needs network access. Unit tests
  don't need real embedding *quality* — they need predictable, fast vectors
  to exercise cache/index mechanics — so ``SentenceTransformer`` is patched
  everywhere with a deterministic, hash-based fake (see ``FakeSentenceTransformer``).
"""

import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pytest
import redis

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval import vector_index as vector_index_module  # noqa: E402

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


class FakeSentenceTransformer:
    """
    Deterministic stand-in for ``sentence_transformers.SentenceTransformer``.

    Encodes text into a fixed-dimension unit vector derived from an MD5
    hash of the text, so identical strings always produce identical
    vectors and different strings produce (effectively random, low
    cosine-similarity) different vectors — enough to exercise exact-match
    and "clearly different" cache/search paths without downloading real
    models. Tests that need two *specific* embeddings to be similar
    construct those vectors directly instead of relying on hash luck.
    """

    def __init__(self, *_args, **_kwargs):
        pass

    def encode(self, texts):
        single = isinstance(texts, str)
        items = [texts] if single else list(texts)
        vectors = [self._vector(t) for t in items]
        return np.array(vectors[0]) if single else np.array(vectors)

    @staticmethod
    def _vector(text: str) -> list:
        digest = hashlib.md5(text.encode("utf-8")).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
        vec = rng.normal(size=vector_index_module.EMBEDDING_DIM)
        return (vec / np.linalg.norm(vec)).tolist()


@pytest.fixture(autouse=True)
def patched_embedding_models(monkeypatch):
    """Replace SentenceTransformer with the deterministic fake everywhere it's imported."""
    import ingestion.pipeline as pipeline_module
    import retrieval.hybrid_search as hybrid_search_module
    import retrieval.semantic_cache as semantic_cache_module

    monkeypatch.setattr(pipeline_module, "SentenceTransformer", FakeSentenceTransformer)
    monkeypatch.setattr(hybrid_search_module, "SentenceTransformer", FakeSentenceTransformer)
    monkeypatch.setattr(semantic_cache_module, "SentenceTransformer", FakeSentenceTransformer)


@pytest.fixture
def redis_client():
    """Real Redis connection, flushed before and after each test. Skips if unreachable."""
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    try:
        client.ping()
    except Exception as exc:
        pytest.skip(f"No Redis reachable at {REDIS_HOST}:{REDIS_PORT} ({exc})")
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture(scope="session")
def redisearch_vector_available():
    """True if the connected Redis has a RediSearch build with VECTOR field support."""
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    try:
        client.ping()
    except Exception:
        return False

    probe_index = "idx:__pytest_vector_probe__"
    try:
        vector_index_module.ensure_index(client, dim=4)
        return True
    except Exception:
        return False
    finally:
        try:
            client.ft(vector_index_module.INDEX_NAME).dropindex(delete_documents=True)
        except Exception:
            pass
        try:
            client.ft(probe_index).dropindex(delete_documents=True)
        except Exception:
            pass


@pytest.fixture
def no_vector_index(monkeypatch):
    """
    Stub out retrieval.vector_index's Redis-writing calls as no-ops.

    Used by tests that exercise pipeline/hybrid-search behavior unrelated
    to the vector index itself (chunking, document CRUD, BM25), so they
    don't require a RediSearch build with VECTOR field support to run.
    """
    import ingestion.pipeline as pipeline_module
    import retrieval.hybrid_search as hybrid_search_module

    def _noop(*_args, **_kwargs):
        return None

    def _empty_search(*_args, **_kwargs):
        return []

    for mod in (pipeline_module, hybrid_search_module):
        monkeypatch.setattr(mod.vector_index, "ensure_index", _noop)
        monkeypatch.setattr(mod.vector_index, "index_chunk", _noop)
        monkeypatch.setattr(mod.vector_index, "delete_chunks", _noop)
    monkeypatch.setattr(hybrid_search_module.vector_index, "knn_search", _empty_search)
