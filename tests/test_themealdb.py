"""
Tests for TheMealDB adapter: transformation, error handling, and integration.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.adapters.themealdb import (
    TheMealDBAdapter,
    transform_meal_to_recipe,
    themealdb_adapter,
)


# Sample TheMealDB response (from real API)
SAMPLE_MEAL = {
    "idMeal": "52772",
    "strMeal": "Teriyaki Chicken Casserole",
    "strCategory": "Chicken",
    "strArea": "Japanese",
    "strInstructions": "Preheat oven to 350° F.\r\nSpray a 9x13-inch pan.\r\nCombine ingredients.",
    "strMealThumb": "https://www.themealdb.com/images/media/meals/wvpsxx1468256321.jpg",
    "strTags": "Meat,Casserole",
    "strIngredient1": "soy sauce",
    "strIngredient2": "chicken breasts",
    "strMeasure1": "3/4 cup",
    "strMeasure2": "2",
}


def test_transform_meal_to_recipe():
    """Transformation correctly maps TheMealDB format to internal schema"""
    result = transform_meal_to_recipe(SAMPLE_MEAL)

    assert result["id"] == "external-52772"
    assert result["title"] == "Teriyaki Chicken Casserole"
    assert result["cuisine"] == "Japanese"
    assert result["source"] == "external"
    assert result["image_url"] == "https://www.themealdb.com/images/media/meals/wvpsxx1468256321.jpg"

    # Ingredients: measure + ingredient
    assert "3/4 cup soy sauce" in result["ingredients"]
    assert "2 chicken breasts" in result["ingredients"]

    # Instructions: split by newlines
    assert len(result["instructions"]) >= 2
    assert "Preheat oven" in result["instructions"][0]

    # Tags: from strTags + strCategory
    assert "Meat" in result["tags"]
    assert "Casserole" in result["tags"]
    assert "Chicken" in result["tags"]


def test_transform_meal_minimal():
    """Transformation handles minimal meal data"""
    minimal = {"idMeal": "123", "strMeal": "Simple Meal"}
    result = transform_meal_to_recipe(minimal)

    assert result["id"] == "external-123"
    assert result["title"] == "Simple Meal"
    assert result["ingredients"] == []
    assert result["instructions"] == ["No instructions provided."]
    assert result["source"] == "external"


def test_adapter_search_returns_empty_on_network_error():
    """Adapter returns empty list on network/API errors (graceful degradation)"""
    adapter = TheMealDBAdapter()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = Exception("Connection failed")

        result = adapter.search_meals("chicken")
        assert result == []


def test_adapter_search_returns_empty_on_timeout():
    """Adapter returns empty list on timeout"""
    import httpx

    adapter = TheMealDBAdapter()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = httpx.TimeoutException("Timed out")

        result = adapter.search_meals("chicken")
        assert result == []


def test_adapter_search_handles_null_meals():
    """Adapter handles API response with meals: null"""
    adapter = TheMealDBAdapter()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"meals": None}
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = adapter.search_meals("xyz123nonexistent")
        assert result == []


def test_adapter_get_by_id_returns_none_on_error():
    """Adapter returns None on lookup error (graceful degradation)"""
    import httpx

    adapter = TheMealDBAdapter()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = httpx.ConnectError("Cannot connect")

        result = adapter.get_meal_by_id("52772")
        assert result is None


@pytest.mark.integration
def test_adapter_search_real_api():
    """Integration test: real TheMealDB search returns valid recipes"""
    adapter = TheMealDBAdapter(timeout=15.0)
    result = adapter.search_meals("Arrabiata")

    # May return 0 or more - API is live
    assert isinstance(result, list)
    for recipe in result:
        assert "id" in recipe
        assert "title" in recipe
        assert recipe["source"] == "external"
        assert recipe["id"].startswith("external-")


@pytest.mark.integration
def test_adapter_lookup_real_api():
    """Integration test: real TheMealDB lookup by id returns valid recipe"""
    adapter = TheMealDBAdapter(timeout=15.0)
    result = adapter.get_meal_by_id("52772")

    assert result is not None
    assert result["id"] == "external-52772"
    assert result["title"] == "Teriyaki Chicken Casserole"
    assert result["source"] == "external"
    assert len(result["ingredients"]) > 0
    assert len(result["instructions"]) > 0
