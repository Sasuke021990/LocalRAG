"""
Redis-based semantic cache implementation to intercept redundant queries
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import hashlib
from datetime import datetime, timedelta

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
                 default_ttl: int = 3600):
        """
        Initialize the SemanticCache.
        
        Args:
            redis_host (str): Redis server host
            redis_port (int): Redis server port
            redis_db (int): Redis database number
            cache_prefix (str): Prefix for cache keys in Redis
            default_ttl (int): Default time-to-live for cached entries (seconds)
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.cache_prefix = cache_prefix
        self.default_ttl = default_ttl
        
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
    
    def _is_semantically_similar(self, query1: str, query2: str, threshold: float = 0.8) -> bool:
        """
        Check if two queries are semantically similar (simplified implementation).
        
        In a real implementation, this would use embeddings to compare queries.
        For now, we'll use string similarity as a placeholder.
        
        Args:
            query1 (str): First query
            query2 (str): Second query
            threshold (float): Similarity threshold
            
        Returns:
            bool: True if queries are similar enough
        """
        # Simplified approach - in real implementation, use embeddings
        # This is a placeholder that could be enhanced with actual semantic similarity
        if not query1 or not query2:
            return False
            
        # Simple string-based similarity (could be replaced with more sophisticated methods)
        q1_lower = query1.lower().strip()
        q2_lower = query2.lower().strip()
        
        # Check if one is a substring of the other (basic similarity)
        if q1_lower in q2_lower or q2_lower in q1_lower:
            return True
            
        # For demonstration, we'll return False to avoid false positives
        # In production, implement proper semantic similarity checking
        return False
    
    def get_cached_result(self, query: str) -> Optional[CachedResult]:
        """
        Retrieve a cached result for the given query.
        
        Args:
            query (str): The search query
            
        Returns:
            CachedResult or None if not found or expired
        """
        if not self.redis_client or not REDIS_AVAILABLE:
            logger.warning("Redis not available - cannot retrieve from cache")
            return None
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(query)
            
            # Get cached data
            cached_data = self.redis_client.get(cache_key)
            if not cached_data:
                logger.debug(f"No cached result found for query: {query}")
                return None
            
            # Parse cached data
            try:
                parsed_data = json.loads(cached_data)
                
                # Check if cache entry is still valid (not expired)
                timestamp = datetime.fromisoformat(parsed_data['timestamp'])
                ttl = parsed_data.get('ttl', self.default_ttl)
                
                if datetime.now() - timestamp > timedelta(seconds=ttl):
                    # Entry expired, remove it
                    self.redis_client.delete(cache_key)
                    logger.debug(f"Cached result expired for query: {query}")
                    return None
                
                # Return cached result
                cached_result = CachedResult(
                    query=query,
                    results=parsed_data['results'],
                    timestamp=timestamp,
                    ttl=ttl
                )
                
                logger.info(f"Cache hit for query: {query}")
                return cached_result
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error parsing cached data for query {query}: {str(e)}")
                # Remove corrupted cache entry
                self.redis_client.delete(cache_key)
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
                'ttl': ttl
            }
            
            # Generate cache key
            cache_key = self._generate_cache_key(query)
            
            # Store in Redis as JSON string with TTL
            json_data = json.dumps(cached_entry)
            self.redis_client.setex(cache_key, ttl, json_data)
            
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
            # Get approximate number of keys matching our prefix
            pattern = f"{self.cache_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            return {
                "redis_connected": True,
                "cache_prefix": self.cache_prefix,
                "cached_entries": len(keys),
                "default_ttl": self.default_ttl
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