"""
Shared Redis connection for the auth module.

Kept as its own client (rather than reaching into main.py's
ingestion_pipeline.redis_client) so backend.auth never depends on
backend.main — main.py depends on auth, not the other way around.
Matches the existing codebase convention of each component owning its
own redis.Redis connection (pipeline, hybrid_search, semantic_cache all
do the same).
"""

import redis

from utils.config import config

redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True,
)
