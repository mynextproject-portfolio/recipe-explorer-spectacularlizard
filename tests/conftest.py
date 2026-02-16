"""
Test fixtures for Recipe Explorer tests.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.storage import recipe_storage


@pytest.fixture
def client():
    """Test client for making requests to the API"""
    return TestClient(app)


@pytest.fixture
def clean_storage():
    """Reset storage before and after each test"""
    recipe_storage.recipes.clear()
    yield
    recipe_storage.recipes.clear()


@pytest.fixture
def sample_recipe_data():
    """Sample recipe for testing"""
    return {
        "title": "Test Recipe",
        "description": "A test recipe",
        "ingredients": ["ingredient 1", "ingredient 2"],
        "instructions": ["First, do step 1.", "Then, do step 2."],
        "tags": ["test"],
        "cuisine": "Test Cuisine"
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
