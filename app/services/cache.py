"""
Redis cache service for external API responses.
Uses 24-hour TTL. Gracefully degrades to no caching when Redis is unavailable.
"""

import json
import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# 24 hours in seconds
CACHE_TTL_SECONDS = 86400

CACHE_KEY_PREFIX = "mealdb:"
CACHE_KEY_SEARCH = f"{CACHE_KEY_PREFIX}search:"
CACHE_KEY_MEAL = f"{CACHE_KEY_PREFIX}meal:"


def _get_redis_client():  # type: ignore
    """Create Redis client from REDIS_URL env, or None if not configured."""
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    if not url or url.lower() in ("", "false", "none", "0"):
        return None
    try:
        import redis

        client = redis.from_url(url, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        logger.warning("Redis unavailable, caching disabled: %s", e)
        return None


_redis_client: Optional[Any] = None


def get_redis() -> Optional[Any]:
    """Get Redis client (lazy init, cached)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = _get_redis_client()
    return _redis_client


def is_available() -> bool:
    """True if Redis cache is configured and reachable."""
    return get_redis() is not None


def cache_get_search(query: str) -> Optional[List[dict[str, Any]]]:
    """Get cached search results. Returns None on miss or error."""
    r = get_redis()
    if r is None:
        return None
    key = f"{CACHE_KEY_SEARCH}{query.strip().lower()}"
    try:
        raw = r.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return data if isinstance(data, list) else None
    except Exception as e:
        logger.debug("Cache get failed for %s: %s", key, e)
        return None


def cache_set_search(query: str, results: List[dict[str, Any]]) -> None:
    """Store search results in cache with 24h TTL."""
    r = get_redis()
    if r is None:
        return
    key = f"{CACHE_KEY_SEARCH}{query.strip().lower()}"
    try:
        r.set(key, json.dumps(results), ex=CACHE_TTL_SECONDS)
    except Exception as e:
        logger.debug("Cache set failed for %s: %s", key, e)


def cache_get_meal(meal_id: str) -> Optional[Any]:
    """
    Get cached meal by ID.
    Returns dict on hit, or special sentinel for 'not found' (cached empty).
    """
    r = get_redis()
    if r is None:
        return None
    key = f"{CACHE_KEY_MEAL}{meal_id.strip()}"
    try:
        raw = r.get(key)
        if raw is None:
            return None
        if raw == "__NONE__":
            return "__CACHED_NONE__"  # Sentinel for cached "not found"
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.debug("Cache get failed for %s: %s", key, e)
        return None


def cache_set_meal(meal_id: str, value: Optional[dict[str, Any]]) -> None:
    """Store meal in cache. Use sentinel for None (not found)."""
    r = get_redis()
    if r is None:
        return
    key = f"{CACHE_KEY_MEAL}{meal_id.strip()}"
    try:
        if value is None:
            r.set(key, "__NONE__", ex=CACHE_TTL_SECONDS)
        else:
            r.set(key, json.dumps(value), ex=CACHE_TTL_SECONDS)
    except Exception as e:
        logger.debug("Cache set failed for %s: %s", key, e)
