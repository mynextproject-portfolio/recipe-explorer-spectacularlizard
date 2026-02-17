"""
Abstractions for data access, external APIs, and caching.
Enables component swapping and testability via dependency injection.
"""

from typing import Any, List, Optional, Protocol

from app.models import Recipe, RecipeCreate, RecipeUpdate


class RecipeRepository(Protocol):
    """Abstract interface for internal recipe data access."""

    def get_all_recipes(self) -> List[Recipe]:
        """Return all recipes."""
        ...

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        """Get a recipe by ID."""
        ...

    def search_recipes(self, query: str) -> List[Recipe]:
        """Search recipes by query."""
        ...

    def create_recipe(self, recipe_data: RecipeCreate) -> Recipe:
        """Create a new recipe."""
        ...

    def update_recipe(
        self, recipe_id: str, recipe_data: RecipeUpdate
    ) -> Optional[Recipe]:
        """Update an existing recipe."""
        ...

    def delete_recipe(self, recipe_id: str) -> bool:
        """Delete a recipe."""
        ...

    def import_recipes(self, recipes_data: List[dict]) -> int:
        """Import recipes from list of dicts. Returns count imported."""
        ...


class ExternalRecipeSource(Protocol):
    """Abstract interface for external recipe API (e.g. TheMealDB)."""

    def search_meals(self, query: str) -> List[dict[str, Any]]:
        """Search external API by query. Returns list of recipe dicts."""
        ...

    def get_meal_by_id(self, meal_id: str) -> Optional[dict[str, Any]]:
        """Get meal by ID. Returns recipe dict or None."""
        ...


class CacheBackend(Protocol):
    """Abstract interface for cache operations (e.g. Redis)."""

    def is_available(self) -> bool:
        """True if cache is configured and reachable."""
        ...

    def get_search(self, query: str) -> Optional[List[dict[str, Any]]]:
        """Get cached search results. Returns None on miss."""
        ...

    def set_search(self, query: str, results: List[dict[str, Any]]) -> None:
        """Store search results in cache."""
        ...

    def get_meal(self, meal_id: str) -> Optional[Any]:
        """Get cached meal. Returns dict, None, or __CACHED_NONE__ sentinel."""
        ...

    def set_meal(self, meal_id: str, value: Optional[dict[str, Any]]) -> None:
        """Store meal in cache. Use None for 'not found' sentinel."""
        ...
