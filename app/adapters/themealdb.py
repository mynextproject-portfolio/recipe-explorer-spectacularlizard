"""
TheMealDB API adapter with proper error handling and data transformation.
Transforms external API format to match internal Recipe schema.
"""
import re
import time
from typing import Any, Callable, List, Optional
import logging

import httpx

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
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._on_request_done = on_request_done

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
        """
        if not query or not str(query).strip():
            return []

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

        self._record_timing((time.perf_counter() - start) * 1000)
        meals = data.get("meals")
        if meals is None:
            return []

        results: list[dict[str, Any]] = []
        for m in meals:
            if isinstance(m, dict):
                try:
                    results.append(transform_meal_to_recipe(m))
                except Exception as e:
                    logger.warning("Failed to transform meal %s: %s", m.get("idMeal"), e)
        return results

    def get_meal_by_id(self, meal_id: str) -> Optional[dict[str, Any]]:
        """
        Lookup full meal details by id. Returns transformed recipe dict or None.
        On error, returns None (graceful degradation).
        """
        if not meal_id or not str(meal_id).strip():
            return None

        url = f"{self.base_url}/lookup.php"
        params = {"i": str(meal_id).strip()}
        start = time.perf_counter()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
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

        self._record_timing((time.perf_counter() - start) * 1000)
        meals = data.get("meals")
        if not meals or not isinstance(meals, list):
            return None

        meal = meals[0] if isinstance(meals[0], dict) else None
        if not meal:
            return None

        try:
            return transform_meal_to_recipe(meal)
        except Exception as e:
            logger.warning("Failed to transform meal %s: %s", meal_id, e)
            return None


# Singleton instance
themealdb_adapter = TheMealDBAdapter()
