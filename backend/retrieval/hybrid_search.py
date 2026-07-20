"""
Hybrid search implementation using BM25 (sparse) and RediSearch vector KNN (dense)
"""

import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import numpy as np

# For BM25 search
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logging.warning("rank-bm25 not available - BM25 search disabled")

# For Redis connection and operations
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("redis not available - Redis integration disabled")

from sentence_transformers import SentenceTransformer

from retrieval import vector_index
from utils.device import get_best_device

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Data class to represent a search result."""
    content: str
    score: float
    metadata: Dict[str, Any]
    source: str

class HybridSearchEngine:
    """
    A hybrid search engine combining BM25 (sparse) and Redis (dense/vector) searches.

    This implementation:
    1. Uses BM25 for keyword-based sparse search
    2. Uses a RediSearch HNSW vector index (see ``retrieval.vector_index``) for
       dense semantic search via cosine-similarity KNN
    3. Fuses results using Reciprocal Rank Fusion (RRF)

    Document ingestion (parsing, chunking, embedding, storage) is owned by
    ``ingestion.pipeline.DocumentIngestionPipeline`` — this class is
    read/query-only.
    """

    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379,
                 redis_db: int = 0, bm25_tokenizer: str = 'english',
                 embedding_model: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the HybridSearchEngine.

        Args:
            redis_host (str): Redis server host
            redis_port (int): Redis server port
            redis_db (int): Redis database number
            bm25_tokenizer (str): Tokenizer for BM25 (default: 'english')
            embedding_model (str): SentenceTransformer model used to embed
                queries — must match the model used to embed documents
                (``ingestion.pipeline``'s default), otherwise cosine
                similarity between query and chunk vectors is meaningless.
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.bm25_tokenizer = bm25_tokenizer

        # Initialize Redis connection
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
                vector_index.ensure_index(self.redis_client)
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                self.redis_client = None
        else:
            logger.warning("Redis client not available - vector search will be disabled")

        # Query embedding model (must match the document embedding model)
        try:
            self.model = SentenceTransformer(embedding_model, device=get_best_device())
            logger.info(f"Loaded query embedding model: {embedding_model}")
        except Exception as e:
            logger.error(f"Failed to load embedding model '{embedding_model}': {str(e)}")
            self.model = None

        # Initialize BM25
        self.bm25 = None
        self.bm25_corpus = []          # tokenised token lists
        self.bm25_corpus_raw = []      # original text strings
        self.bm25_doc_meta = []        # parallel metadata dicts
        self.bm25_doc_ids = []
        if BM25_AVAILABLE:
            logger.info("BM25 search engine initialized")
        else:
            logger.warning("BM25 search engine not available")
    
    def setup_bm25_index(self, documents: List[Dict[str, Any]]) -> None:
        """
        Setup BM25 index from a list of documents.

        Each document dict must have a ``content`` field. Optional keys
        ``file_name``, ``category``, and ``chunk_index`` are preserved as
        metadata so that search results carry proper attribution.
        """
        if not BM25_AVAILABLE:
            logger.warning("BM25 not available - skipping setup")
            return

        try:
            self.bm25_corpus     = []
            self.bm25_corpus_raw = []
            self.bm25_doc_meta   = []
            self.bm25_doc_ids    = []

            for i, doc in enumerate(documents):
                content = doc.get('content', '') or ''
                tokens  = content.lower().split()
                self.bm25_corpus.append(tokens)
                self.bm25_corpus_raw.append(content)
                self.bm25_doc_ids.append(str(i))
                self.bm25_doc_meta.append({
                    'file_name':   doc.get('file_name', 'Unknown'),
                    'category':    doc.get('category',  'General'),
                    'chunk_index': doc.get('chunk_index', i),
                })

            self.bm25 = BM25Okapi(self.bm25_corpus)
            logger.info(f"BM25 index created with {len(self.bm25_corpus)} documents")

        except Exception as e:
            logger.error(f"Error setting up BM25 index: {str(e)}")
            self.bm25 = None
    
    def search_bm25(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """BM25 keyword search — returns results with real content and metadata."""
        if not self.bm25 or not BM25_AVAILABLE:
            logger.warning("BM25 not available for search")
            return []

        try:
            query_tokens  = query.lower().split()
            bm25_scores   = self.bm25.get_scores(query_tokens)
            top_indices   = np.argsort(bm25_scores)[::-1][:top_k]

            results = []
            for idx in top_indices:
                if bm25_scores[idx] > 0:
                    meta = self.bm25_doc_meta[idx] if idx < len(self.bm25_doc_meta) else {}
                    results.append(SearchResult(
                        content  = self.bm25_corpus_raw[idx] if idx < len(self.bm25_corpus_raw) else ' '.join(self.bm25_corpus[idx]),
                        score    = float(bm25_scores[idx]),
                        metadata = meta,
                        source   = 'bm25',
                    ))

            logger.info(f"BM25 search returned {len(results)} results for query: '{query}'")
            return results

        except Exception as e:
            logger.error(f"Error in BM25 search: {str(e)}")
            return []
    
    def search_redis(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        Dense/vector search: embeds ``query`` with the same model used to
        embed documents, then runs a RediSearch KNN cosine-similarity query
        against the per-chunk vector index (``retrieval.vector_index``).
        Falls back to an empty list if Redis/the embedding model is
        unavailable or no documents have been indexed yet.
        """
        if not self.redis_client or not REDIS_AVAILABLE:
            logger.warning("Redis not available for search")
            return []
        if not self.model:
            logger.warning("Embedding model not available - skipping vector search")
            return []

        try:
            if not self.redis_client.keys("document:*"):
                logger.info("Redis has no document keys — skipping vector search")
                return []

            query_embedding = self.model.encode(query).tolist()
            hits = vector_index.knn_search(self.redis_client, query_embedding, top_k)

            results = [
                SearchResult(
                    content=hit['content'],
                    score=hit['score'],
                    metadata={
                        'file_name':   hit['file_name'],
                        'category':    hit['category'],
                        'chunk_index': hit['chunk_index'],
                    },
                    source='vector',
                )
                for hit in hits
            ]
            logger.info(f"Vector search returned {len(results)} results for query: '{query}'")
            return results

        except Exception as e:
            logger.error(f"Error in vector search: {str(e)}")
            return []
    
    def fuse_results(
        self,
        bm25_results: List[SearchResult],
        redis_results: List[SearchResult],
        k: int = 20,
    ) -> List[SearchResult]:
        """
        Reciprocal Rank Fusion of BM25 and Redis results.

        Deduplicates by content, propagates real metadata from source results,
        and returns at most *k* fused ``SearchResult`` objects.
        """
        try:
            # Map content -> (best SearchResult, accumulated RRF score)
            fused: Dict[str, Any] = {}

            for rank, result in enumerate(bm25_results):
                key = result.content[:200]  # deduplicate by first 200 chars
                rrf = 1.0 / (60 + rank + 1)
                if key not in fused:
                    fused[key] = {'result': result, 'score': 0.0}
                fused[key]['score'] += rrf

            for rank, result in enumerate(redis_results):
                key = result.content[:200]
                rrf = 1.0 / (60 + rank + 1)
                if key not in fused:
                    fused[key] = {'result': result, 'score': 0.0}
                fused[key]['score'] += rrf

            sorted_items = sorted(fused.values(), key=lambda x: x['score'], reverse=True)

            top_results = []
            for item in sorted_items[:k]:
                r = item['result']
                top_results.append(SearchResult(
                    content  = r.content,
                    score    = item['score'],
                    metadata = r.metadata,
                    source   = 'fused',
                ))

            logger.info(f"RRF fusion: {len(fused)} unique chunks → top {len(top_results)}")
            return top_results

        except Exception as e:
            logger.error(f"Error in result fusion: {str(e)}")
            return []
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        Hybrid search: auto-loads the BM25 index from Redis if not yet built,
        then combines BM25 (sparse) + vector KNN (dense) results with RRF fusion.
        """
        logger.info(f"Performing hybrid search for query: '{query}'")

        # Auto-populate BM25 from Redis if the index is empty
        if not self.bm25 and self.redis_client:
            try:
                import json as _json
                docs_for_bm25 = []
                for key in (self.redis_client.keys('document:*') or []):
                    raw = self.redis_client.get(key)
                    if not raw:
                        continue
                    try:
                        doc = _json.loads(raw)
                    except Exception:
                        continue
                    file_name = doc.get('file_name', 'Unknown')
                    category  = doc.get('category',  'General')
                    for ci, chunk_text in enumerate(doc.get('chunks', [])):
                        docs_for_bm25.append({
                            'content':     chunk_text,
                            'file_name':   file_name,
                            'category':    category,
                            'chunk_index': ci,
                        })
                if docs_for_bm25:
                    self.setup_bm25_index(docs_for_bm25)
                    logger.info(f"BM25 auto-loaded {len(docs_for_bm25)} chunks from Redis")
            except Exception as exc:
                logger.error(f"BM25 auto-load failed: {exc}")

        bm25_results  = self.search_bm25(query, top_k * 2)
        redis_results = self.search_redis(query, top_k * 2)
        fused_results = self.fuse_results(bm25_results, redis_results, top_k)

        logger.info(f"Hybrid search completed with {len(fused_results)} results")
        return fused_results
    
    def get_search_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the search engine.

        Returns:
            Dictionary with search engine statistics
        """
        vector_doc_count = 0
        if self.redis_client:
            try:
                vector_doc_count = int(self.redis_client.ft(vector_index.INDEX_NAME).info().get('num_docs', 0))
            except Exception:
                pass

        return {
            "bm25_available": BM25_AVAILABLE,
            "redis_available": REDIS_AVAILABLE,
            "redis_connected": self.redis_client is not None,
            "bm25_corpus_size": len(self.bm25_corpus) if self.bm25_corpus else 0,
            "vector_index_size": vector_doc_count,
        }