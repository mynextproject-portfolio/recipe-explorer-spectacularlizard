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


class RedisCacheBackend:
    """
    Redis-backed cache implementation for DI.
    Implements CacheBackend protocol. Can be injected into adapters.
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self._redis_url = redis_url or os.environ.get(
            "REDIS_URL", "redis://localhost:6379/0"
        )
        self._client: Optional[Any] = None

    def _get_client(self) -> Optional[Any]:
        if self._redis_url and self._redis_url.lower() not in (
            "",
            "false",
            "none",
            "0",
        ):
            try:
                import redis

                client = redis.from_url(self._redis_url, decode_responses=True)
                client.ping()
                return client
            except Exception as e:
                logger.warning("Redis unavailable, caching disabled: %s", e)
        return None

    def is_available(self) -> bool:
        if self._client is None:
            self._client = self._get_client()
        return self._client is not None

    def get_search(self, query: str) -> Optional[List[dict[str, Any]]]:
        r = self._client if self._client is not None else self._get_client()
        if r is None:
            return None
        self._client = r
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

    def set_search(self, query: str, results: List[dict[str, Any]]) -> None:
        r = self._client if self._client is not None else self._get_client()
        if r is None:
            return
        self._client = r
        key = f"{CACHE_KEY_SEARCH}{query.strip().lower()}"
        try:
            r.set(key, json.dumps(results), ex=CACHE_TTL_SECONDS)
        except Exception as e:
            logger.debug("Cache set failed for %s: %s", key, e)

    def get_meal(self, meal_id: str) -> Optional[Any]:
        r = self._client if self._client is not None else self._get_client()
        if r is None:
            return None
        self._client = r
        key = f"{CACHE_KEY_MEAL}{meal_id.strip()}"
        try:
            raw = r.get(key)
            if raw is None:
                return None
            if raw == "__NONE__":
                return "__CACHED_NONE__"
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception as e:
            logger.debug("Cache get failed for %s: %s", key, e)
            return None

    def set_meal(self, meal_id: str, value: Optional[dict[str, Any]]) -> None:
        r = self._client if self._client is not None else self._get_client()
        if r is None:
            return
        self._client = r
        key = f"{CACHE_KEY_MEAL}{meal_id.strip()}"
        try:
            if value is None:
                r.set(key, "__NONE__", ex=CACHE_TTL_SECONDS)
            else:
                r.set(key, json.dumps(value), ex=CACHE_TTL_SECONDS)
        except Exception as e:
            logger.debug("Cache set failed for %s: %s", key, e)


class NoOpCacheBackend:
    """
    No-op cache for testing or when Redis is not desired.
    Implements CacheBackend protocol; all operations are no-ops.
    """

    def is_available(self) -> bool:
        return False

    def get_search(self, query: str) -> Optional[List[dict[str, Any]]]:
        return None

    def set_search(self, query: str, results: List[dict[str, Any]]) -> None:
        pass

    def get_meal(self, meal_id: str) -> Optional[Any]:
        return None

    def set_meal(self, meal_id: str, value: Optional[dict[str, Any]]) -> None:
        pass
