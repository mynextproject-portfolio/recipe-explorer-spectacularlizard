"""
TheMealDB API adapter with proper error handling and data transformation.
Transforms external API format to match internal Recipe schema.
Redis caching for external API responses (24h TTL) via injected CacheBackend.
"""

import re
import time
from typing import Any, Callable, List, Optional, TYPE_CHECKING
import logging

import httpx

from app.services.cache import NoOpCacheBackend

if TYPE_CHECKING:
    from app.core.abstractions import CacheBackend

logger = logging.getLogger(__name__)

BASE_URL = "https://www.themealdb.com/api/json/v1/1"
DEFAULT_TIMEOUT = 10.0


def _build_ingredients(meal: dict[str, Any]) -> list[str]:
    """Build ingredients list from strIngredient1-20 and strMeasure1-20."""
    ingredients: list[str] = []
    for i in range(1, 21):
        ing_key = f"strIngredient{i}"
        measure_key = f"strMeasure{i}"
        ing = meal.get(ing_key)
        measure = meal.get(measure_key)
        if ing and str(ing).strip():
            measure_str = str(measure).strip() if measure else ""
            if measure_str:
                ingredients.append(f"{measure_str} {ing}".strip())
            else:
                ingredients.append(str(ing).strip())
    return ingredients


def _build_instructions(meal: dict[str, Any]) -> list[str]:
    """Split strInstructions into step-by-step list."""
    raw = meal.get("strInstructions") or ""
    if not raw:
        return ["No instructions provided."]
    # Split by common delimiters: \r\n, \n, numbered steps
    steps = []
    for part in raw.replace("\r\n", "\n").split("\n"):
        part = part.strip()
        if part:
            # Remove leading numbers/dots (e.g. "1. ", "2) ")
            part = re.sub(r"^\d+[\.\)]\s*", "", part)
            if part:
                steps.append(part)
    return steps if steps else [raw]


def _build_tags(meal: dict[str, Any]) -> list[str]:
    """Build tags from strTags and strCategory."""
    tags: list[str] = []
    raw_tags = meal.get("strTags")
    if raw_tags and str(raw_tags).strip():
        tags.extend(t.strip() for t in str(raw_tags).split(",") if t.strip())
    category = meal.get("strCategory")
    if category and str(category).strip():
        tags.append(str(category).strip())
    return tags


def transform_meal_to_recipe(meal: dict[str, Any]) -> dict[str, Any]:
    """
    Transform TheMealDB meal object to internal Recipe-compatible schema.
    Returns a dict with: id, title, description, ingredients, instructions,
    tags, cuisine, source, image_url.
    """
    meal_id = str(meal.get("idMeal", ""))
    title = meal.get("strMeal") or "Untitled"
    instructions_list = _build_instructions(meal)
    description = instructions_list[0] if instructions_list else ""
    if len(instructions_list) > 1:
        description = f"{description}..." if len(description) > 100 else description

    return {
        "id": f"external-{meal_id}",
        "title": title,
        "description": description or title,
        "ingredients": _build_ingredients(meal),
        "instructions": instructions_list,
        "tags": _build_tags(meal),
        "cuisine": meal.get("strArea") or None,
        "source": "external",
        "image_url": meal.get("strMealThumb"),
        "external_id": meal_id,
    }


class TheMealDBAdapter:
    """Adapter for TheMealDB API with error handling."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        on_request_done: Optional[Callable[[float], None]] = None,
        cache: Optional["CacheBackend"] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._on_request_done = on_request_done
        self._cache = cache if cache is not None else NoOpCacheBackend()

    def _record_timing(self, elapsed_ms: float) -> None:
        """Call timing callback if configured."""
        if self._on_request_done is not None:
            try:
                self._on_request_done(elapsed_ms)
            except Exception as e:
                logger.debug("Timing callback error: %s", e)

    def search_meals(self, query: str) -> List[dict[str, Any]]:
        """
        Search meals by name. Returns list of transformed recipe dicts.
        On error, returns empty list (graceful degradation).
        Uses Redis cache when available (24h TTL).
        """
        if not query or not str(query).strip():
            return []

        # Check cache first (when cache backend is available)
        if self._cache.is_available():
            try:
                from app.services.metrics import record_cache_hit, record_cache_miss

                cached = self._cache.get_search(query)
                if cached is not None:
                    record_cache_hit()
                    self._record_timing(0)
                    return cached
                record_cache_miss()
            except Exception:
                pass

        url = f"{self.base_url}/search.php"
        params = {"s": str(query).strip()}
        start = time.perf_counter()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
            logger.warning("TheMealDB search timed out: %s", e)
            self._record_timing((time.perf_counter() - start) * 1000)
            return []
        except httpx.ConnectError as e:
            logger.warning("TheMealDB connection failed: %s", e)
            self._record_timing((time.perf_counter() - start) * 1000)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning("TheMealDB HTTP error %s: %s", e.response.status_code, e)
            self._record_timing((time.perf_counter() - start) * 1000)
            return []
        except Exception as e:
            logger.warning("TheMealDB unexpected error: %s", e)
            self._record_timing((time.perf_counter() - start) * 1000)
            return []

        elapsed_ms = (time.perf_counter() - start) * 1000
        self._record_timing(elapsed_ms)
        meals = data.get("meals")
        if meals is None:
            results = []
        else:
            results = []
            for m in meals:
                if isinstance(m, dict):
                    try:
                        results.append(transform_meal_to_recipe(m))
                    except Exception as e:
                        logger.warning(
                            "Failed to transform meal %s: %s", m.get("idMeal"), e
                        )

        try:
            self._cache.set_search(query, results)
        except Exception:
            pass
        return results

    def get_meal_by_id(self, meal_id: str) -> Optional[dict[str, Any]]:
        """
        Lookup full meal details by id. Returns transformed recipe dict or None.
        On error, returns None (graceful degradation).
        Uses Redis cache when available (24h TTL).
        """
        if not meal_id or not str(meal_id).strip():
            return None

        # Check cache first (when cache backend is available)
        if self._cache.is_available():
            try:
                from app.services.metrics import record_cache_hit, record_cache_miss

                cached = self._cache.get_meal(meal_id)
                if cached is not None:
                    if cached == "__CACHED_NONE__":
                        record_cache_hit()
                        self._record_timing(0)
                        return None
                    record_cache_hit()
                    self._record_timing(0)
                    return cached
                record_cache_miss()
            except Exception:
                pass

        url = f"{self.base_url}/lookup.php"
        params = {"i": str(meal_id).strip()}
        start = time.perf_counter()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.warning("TheMealDB lookup timed out: %s", meal_id)
            self._record_timing((time.perf_counter() - start) * 1000)
            return None
        except httpx.ConnectError as e:
            logger.warning("TheMealDB connection failed: %s", e)
            self._record_timing((time.perf_counter() - start) * 1000)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning("TheMealDB HTTP error: %s", e)
            self._record_timing((time.perf_counter() - start) * 1000)
            return None
        except Exception as e:
            logger.warning("TheMealDB unexpected error: %s", e)
            self._record_timing((time.perf_counter() - start) * 1000)
            return None

        elapsed_ms = (time.perf_counter() - start) * 1000
        self._record_timing(elapsed_ms)
        meals = data.get("meals")
        if not meals or not isinstance(meals, list):
            try:
                self._cache.set_meal(meal_id, None)
            except Exception:
                pass
            return None

        meal = meals[0] if isinstance(meals[0], dict) else None
        if not meal:
            try:
                self._cache.set_meal(meal_id, None)
            except Exception:
                pass
            return None

        try:
            result = transform_meal_to_recipe(meal)
            try:
                self._cache.set_meal(meal_id, result)
            except Exception:
                pass
            return result
        except Exception as e:
            logger.warning("Failed to transform meal %s: %s", meal_id, e)
            return None
