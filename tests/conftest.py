"""
Test fixtures for Recipe Explorer tests.
"""

import os
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.metrics import aggregate_metrics
from app.services.storage import recipe_storage

# Disable Redis cache during tests (no Redis required)
os.environ.setdefault("REDIS_URL", "")


@pytest.fixture
def mock_themealdb():
    """Mock TheMealDB adapter to avoid real API calls. Returns empty by default."""
    mock = MagicMock()
    mock.search_meals.return_value = []
    mock.get_meal_by_id.return_value = None
    with patch("app.routes.api.themealdb_adapter", mock):
        yield mock


@pytest.fixture
def client(mock_themealdb):
    """Test client for making requests to the API"""
    return TestClient(app)


@pytest.fixture
def clean_storage():
    """Reset storage before and after each test"""
    recipe_storage.recipes.clear()
    yield
    recipe_storage.recipes.clear()


@pytest.fixture(autouse=True)
def reset_aggregate_metrics():
    """Reset aggregate metrics before each test for consistent assertions."""
    aggregate_metrics.internal_count = 0
    aggregate_metrics.external_count = 0
    aggregate_metrics.internal_total_ms = 0.0
    aggregate_metrics.external_total_ms = 0.0
    aggregate_metrics.cache_hits = 0
    aggregate_metrics.cache_misses = 0
    yield


@pytest.fixture
def sample_recipe_data():
    """Sample recipe for testing"""
    return {
        "title": "Test Recipe",
        "description": "A test recipe",
        "ingredients": ["ingredient 1", "ingredient 2"],
        "instructions": ["First, do step 1.", "Then, do step 2."],
        "tags": ["test"],
        "cuisine": "Test Cuisine",
    }


@pytest.fixture
def valid_import_json():
    """Valid recipes JSON for import testing"""
    return [
        {
            "id": "import-test-001",
            "title": "Imported Recipe",
            "description": "An imported test recipe",
            "ingredients": ["flour", "water"],
            "instructions": ["Mix ingredients", "Bake"],
            "tags": ["imported"],
            "cuisine": "Test",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
    ]
