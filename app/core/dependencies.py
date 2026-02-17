"""
FastAPI dependency injection providers.
Use Depends(get_recipe_storage), etc. in route handlers.
"""

from typing import Optional

from app.adapters.themealdb import TheMealDBAdapter
from app.core.abstractions import CacheBackend, ExternalRecipeSource, RecipeRepository
from app.services.cache import NoOpCacheBackend, RedisCacheBackend
from app.services.storage import RecipeStorage

# --- Singletons (lazy-initialized) ---

_recipe_storage: Optional[RecipeStorage] = None
_external_source: Optional[TheMealDBAdapter] = None
_cache_backend: Optional[CacheBackend] = None


def get_recipe_storage() -> RecipeRepository:
    """Provide RecipeRepository. Used as Depends(get_recipe_storage)."""
    global _recipe_storage
    if _recipe_storage is None:
        _recipe_storage = RecipeStorage()
    return _recipe_storage


def get_external_recipe_source() -> ExternalRecipeSource:
    """Provide ExternalRecipeSource (TheMealDB). Used as Depends(get_external_recipe_source)."""
    global _external_source
    if _external_source is None:
        _external_source = TheMealDBAdapter(cache=get_cache_backend())
    return _external_source


def get_cache_backend() -> CacheBackend:
    """Provide CacheBackend. Used as Depends(get_cache_backend) or for adapter construction."""
    global _cache_backend
    if _cache_backend is None:
        _cache_backend = RedisCacheBackend()
    return _cache_backend


def get_noop_cache() -> CacheBackend:
    """Provide NoOpCacheBackend for testing. Override get_cache_backend with this."""
    return NoOpCacheBackend()


# --- Factory for test overrides ---


def create_fresh_recipe_storage() -> RecipeStorage:
    """Create new RecipeStorage instance. Use in tests for clean state."""
    return RecipeStorage()


def create_mock_external_source(cache: Optional[CacheBackend] = None) -> TheMealDBAdapter:
    """Create TheMealDBAdapter with optional cache. Use in tests with custom cache."""
    return TheMealDBAdapter(cache=cache or NoOpCacheBackend())
