"""
RediSearch vector index over per-chunk embeddings.

``ingestion.pipeline`` stores each document as a single JSON-blob STRING
keyed ``document:<category>:<file_name>`` (chunks + embeddings as parallel
lists). RediSearch can only index HASH or JSON documents, not opaque
STRINGs, so this module maintains a second, *derived* representation: one
HASH per chunk (``chunk:<category>:<file_name>:<chunk_index>``) indexed by
an HNSW vector field, letting queries do a real cosine-similarity KNN
search instead of scanning/scoring every chunk in Python.

The chunk HASHes are fully rebuildable from the ``document:*`` blobs (or
their JSON disk backups) at any time — see
``DocumentIngestionPipeline.reindex_from_disk``, which re-populates this
index on every startup.
"""

import logging
from typing import Any, Dict, List

import numpy as np
from redis import Redis
from redis.commands.search.field import NumericField, TagField, TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

logger = logging.getLogger(__name__)

INDEX_NAME = "idx:chunks"
CHUNK_KEY_PREFIX = "chunk:"
EMBEDDING_DIM = 384


def chunk_key(category: str, file_name: str, chunk_index: int) -> str:
    """Deterministic key for one chunk — no KEYS/SCAN needed to delete it later."""
    return f"{CHUNK_KEY_PREFIX}{category}:{file_name}:{chunk_index}"


def ensure_index(redis_client: Redis, dim: int = EMBEDDING_DIM) -> None:
    """
    Create the RediSearch chunk vector index if it doesn't already exist.

    Idempotent and safe to call from multiple constructors / every process
    start — swallows "index already exists" so callers never need to
    coordinate who creates it first.
    """
    try:
        redis_client.ft(INDEX_NAME).info()
        return
    except Exception:
        pass

    schema = (
        TextField("content"),
        TagField("file_name"),
        TagField("category"),
        NumericField("chunk_index"),
        VectorField(
            "embedding",
            "HNSW",
            {
                "TYPE": "FLOAT32",
                "DIM": dim,
                "DISTANCE_METRIC": "COSINE",
            },
        ),
    )
    definition = IndexDefinition(prefix=[CHUNK_KEY_PREFIX], index_type=IndexType.HASH)
    try:
        redis_client.ft(INDEX_NAME).create_index(fields=schema, definition=definition)
        logger.info(f"Created RediSearch vector index '{INDEX_NAME}' (dim={dim})")
    except Exception as exc:
        if "already exists" in str(exc).lower():
            return
        logger.error(f"Failed to create vector index '{INDEX_NAME}': {exc}")
        raise


def index_chunk(
    redis_client: Redis,
    category: str,
    file_name: str,
    chunk_index: int,
    content: str,
    embedding: List[float],
) -> None:
    """Write/overwrite one chunk HASH. Idempotent — safe to call repeatedly (e.g. on reindex)."""
    key = chunk_key(category, file_name, chunk_index)
    vector_bytes = np.array(embedding, dtype=np.float32).tobytes()
    redis_client.hset(
        key,
        mapping={
            "content": content,
            "file_name": file_name,
            "category": category,
            "chunk_index": chunk_index,
            "embedding": vector_bytes,
        },
    )


def delete_chunks(redis_client: Redis, category: str, file_name: str, chunk_count: int) -> None:
    """Delete all chunk HASHes for a document by reconstructing their deterministic keys."""
    if chunk_count <= 0:
        return
    keys = [chunk_key(category, file_name, i) for i in range(chunk_count)]
    redis_client.delete(*keys)


def knn_search(redis_client: Redis, query_embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Run a RediSearch KNN vector query and return chunk hits sorted by
    similarity (highest first). Returns ``[]`` on any failure (e.g. index
    not yet created, no chunks indexed) rather than raising, matching the
    fail-soft convention used elsewhere in the retrieval layer.
    """
    vector_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
    query = (
        Query(f"*=>[KNN {top_k} @embedding $vec AS score]")
        .sort_by("score")
        .return_fields("content", "file_name", "category", "chunk_index", "score")
        .dialect(2)
    )
    try:
        response = redis_client.ft(INDEX_NAME).search(query, query_params={"vec": vector_bytes})
    except Exception as exc:
        logger.error(f"KNN vector search failed: {exc}")
        return []

    results = []
    for doc in response.docs:
        distance = float(doc.score)
        results.append(
            {
                "content": doc.content,
                "file_name": doc.file_name,
                "category": doc.category,
                "chunk_index": int(doc.chunk_index),
                # COSINE distance is in [0, 2]; convert to a similarity score
                # (higher = more relevant) so it's comparable to BM25 scores.
                "score": 1.0 - distance,
            }
        )
    return results
