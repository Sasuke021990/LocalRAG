"""
Redis-based semantic cache implementation to intercept redundant queries
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import hashlib
from datetime import datetime, timedelta

import numpy as np
from sentence_transformers import SentenceTransformer

from utils.device import get_best_device

# For Redis connection and operations
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("redis not available - semantic cache disabled")

logger = logging.getLogger(__name__)

@dataclass
class CachedResult:
    """Data class to represent a cached search result."""
    query: str
    results: List[Dict[str, Any]]
    timestamp: datetime
    ttl: int  # Time-to-live in seconds

class SemanticCache:
    """
    Redis-based semantic cache for intercepting redundant queries.
    
    This cache stores query-result pairs and returns cached responses 
    instantly for semantically similar queries without hitting the LLM.
    """
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379,
                 redis_db: int = 0, cache_prefix: str = "semantic_cache:",
                 default_ttl: int = 3600, embedding_model: str = 'all-MiniLM-L6-v2',
                 similarity_threshold: float = 0.92):
        """
        Initialize the SemanticCache.

        Args:
            redis_host (str): Redis server host
            redis_port (int): Redis server port
            redis_db (int): Redis database number
            cache_prefix (str): Prefix for cache keys in Redis
            default_ttl (int): Default time-to-live for cached entries (seconds)
            embedding_model (str): SentenceTransformer model used to embed
                queries for similarity lookups
            similarity_threshold (float): Minimum cosine similarity for a
                past query to count as a cache hit. Deliberately
                conservative (default 0.92) to avoid returning a stale
                answer for a genuinely different question.
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.cache_prefix = cache_prefix
        self.default_ttl = default_ttl
        self.similarity_threshold = similarity_threshold
        # Redis SET of active cache keys, maintained alongside the entries
        # themselves so a semantic-similarity lookup can iterate a small
        # candidate set instead of scanning with KEYS on every query.
        self.index_key = f"{cache_prefix}__index__"

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
                logger.info(f"Connected to Redis for semantic cache at {redis_host}:{redis_port}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis for semantic cache: {str(e)}")
                self.redis_client = None
        else:
            logger.warning("Redis client not available - semantic cache will be disabled")

        # Embedding model for semantic similarity lookups
        try:
            self.model = SentenceTransformer(embedding_model, device=get_best_device())
            logger.info(f"Loaded semantic cache embedding model: {embedding_model}")
        except Exception as e:
            logger.error(f"Failed to load embedding model '{embedding_model}': {str(e)}")
            self.model = None
    
    def _generate_cache_key(self, query: str) -> str:
        """
        Generate a cache key for a given query.
        
        Args:
            query (str): The search query
            
        Returns:
            str: Cache key
        """
        # Create a hash of the query to generate a consistent key
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{self.cache_prefix}{query_hash}"
    
    def _embed(self, query: str) -> Optional[List[float]]:
        """Embed a query with the cache's model. Returns None if unavailable."""
        if not self.model or not query:
            return None
        return self.model.encode(query).tolist()

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        a, b = np.array(vec_a), np.array(vec_b)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def _is_semantically_similar(self, embedding1: List[float], embedding2: List[float],
                                  threshold: Optional[float] = None) -> bool:
        """
        Check if two query embeddings are semantically similar via cosine
        similarity against ``threshold`` (defaults to ``self.similarity_threshold``).
        """
        if not embedding1 or not embedding2:
            return False
        threshold = self.similarity_threshold if threshold is None else threshold
        return self._cosine_similarity(embedding1, embedding2) >= threshold
    
    def _load_entry(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Load and validate a raw cache entry by key. Removes it (from the
        entry key and the key-index SET) if missing, expired, or corrupted.
        Returns the parsed dict, or None.
        """
        cached_data = self.redis_client.get(cache_key)
        if not cached_data:
            self.redis_client.srem(self.index_key, cache_key)
            return None

        try:
            parsed_data = json.loads(cached_data)
            timestamp = datetime.fromisoformat(parsed_data['timestamp'])
            ttl = parsed_data.get('ttl', self.default_ttl)

            if datetime.now() - timestamp > timedelta(seconds=ttl):
                self.redis_client.delete(cache_key)
                self.redis_client.srem(self.index_key, cache_key)
                return None

            return parsed_data
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing cached entry '{cache_key}': {str(e)}")
            self.redis_client.delete(cache_key)
            self.redis_client.srem(self.index_key, cache_key)
            return None

    def get_cached_result(self, query: str) -> Optional[CachedResult]:
        """
        Retrieve a cached result for the given query: first an exact
        (MD5-hash) match, then — if that misses and an embedding model is
        available — the most similar past query above
        ``self.similarity_threshold``.

        Args:
            query (str): The search query

        Returns:
            CachedResult or None if not found or expired
        """
        if not self.redis_client or not REDIS_AVAILABLE:
            logger.warning("Redis not available - cannot retrieve from cache")
            return None

        try:
            # 1. Exact-match fast path
            cache_key = self._generate_cache_key(query)
            parsed_data = self._load_entry(cache_key)
            if parsed_data:
                logger.info(f"Cache hit (exact) for query: {query}")
                return CachedResult(
                    query=query,
                    results=parsed_data['results'],
                    timestamp=datetime.fromisoformat(parsed_data['timestamp']),
                    ttl=parsed_data.get('ttl', self.default_ttl),
                )

            # 2. Semantic-similarity fallback
            query_embedding = self._embed(query)
            if not query_embedding:
                return None

            best_match, best_score = None, 0.0
            for candidate_key in self.redis_client.smembers(self.index_key):
                if candidate_key == cache_key:
                    continue
                candidate = self._load_entry(candidate_key)
                if not candidate or not candidate.get('embedding'):
                    continue
                score = self._cosine_similarity(query_embedding, candidate['embedding'])
                if score >= self.similarity_threshold and score > best_score:
                    best_match, best_score = candidate, score

            if best_match:
                logger.info(
                    f"Cache hit (semantic, score={best_score:.4f}) for query: "
                    f"'{query}' ~ '{best_match.get('query')}'"
                )
                return CachedResult(
                    query=query,
                    results=best_match['results'],
                    timestamp=datetime.fromisoformat(best_match['timestamp']),
                    ttl=best_match.get('ttl', self.default_ttl),
                )

            logger.debug(f"No cached result found for query: {query}")
            return None

        except Exception as e:
            logger.error(f"Error retrieving from cache: {str(e)}")
            return None

    def set_cached_result(self, query: str, results: List[Dict[str, Any]],
                         ttl: int = None) -> bool:
        """
        Store a result in the semantic cache.

        Args:
            query (str): The search query
            results (List): List of search results to cache
            ttl (int): Time-to-live for this entry (seconds)

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.redis_client or not REDIS_AVAILABLE:
            logger.warning("Redis not available - cannot store in cache")
            return False

        try:
            # Use default TTL if not specified
            if ttl is None:
                ttl = self.default_ttl

            # Create cache entry
            cached_entry = {
                'query': query,
                'results': results,
                'timestamp': datetime.now().isoformat(),
                'ttl': ttl,
                'embedding': self._embed(query),
            }

            # Generate cache key
            cache_key = self._generate_cache_key(query)

            # Store in Redis as JSON string with TTL
            json_data = json.dumps(cached_entry)
            self.redis_client.setex(cache_key, ttl, json_data)
            self.redis_client.sadd(self.index_key, cache_key)

            logger.info(f"Stored cached result for query: {query} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Error storing in cache: {str(e)}")
            return False
    
    def clear_cache(self) -> bool:
        """
        Clear all entries from the semantic cache.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.redis_client or not REDIS_AVAILABLE:
            logger.warning("Redis not available - cannot clear cache")
            return False
        
        try:
            # Get all keys matching our prefix and delete them
            pattern = f"{self.cache_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} entries from semantic cache")
            else:
                logger.debug("No entries found to clear from semantic cache")
                
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the semantic cache.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.redis_client or not REDIS_AVAILABLE:
            return {"error": "Redis not available"}
        
        try:
            # Get approximate number of keys matching our prefix (excluding
            # the key-index SET itself, which isn't a cache entry)
            pattern = f"{self.cache_prefix}*"
            keys = [k for k in self.redis_client.keys(pattern) if k != self.index_key]

            return {
                "redis_connected": True,
                "cache_prefix": self.cache_prefix,
                "cached_entries": len(keys),
                "default_ttl": self.default_ttl,
                "similarity_threshold": self.similarity_threshold,
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"error": str(e), "redis_connected": False}
    
    def is_cache_available(self) -> bool:
        """
        Check if semantic cache is available.
        
        Returns:
            bool: True if cache is available and functional
        """
        return self.redis_client is not None and REDIS_AVAILABLE