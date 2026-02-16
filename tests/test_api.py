"""
Smoke and contract tests for Recipe Explorer API.
Covers all endpoints, HTTP status codes (400, 404, 422), and validation.
"""

import io
import json


def test_health_check(client):
    """Smoke test: API is running and responding"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_home_page_loads(client):
    """Smoke test: Home page renders without error"""
    response = client.get("/")
    assert response.status_code == 200
    assert "Recipe Explorer" in response.text


def test_get_all_recipes(client, clean_storage):
    """Contract test: GET /api/recipes returns correct structure"""
    response = client.get("/api/recipes")
    assert response.status_code == 200
    data = response.json()
    assert "recipes" in data
    assert isinstance(data["recipes"], list)


def test_create_and_get_recipe(client, clean_storage, sample_recipe_data):
    """Contract test: Create recipe and verify response structure"""
    # Create recipe
    create_response = client.post("/api/recipes", json=sample_recipe_data)
    assert create_response.status_code == 200
    
    recipe = create_response.json()
    assert "id" in recipe
    assert "title" in recipe
    assert "created_at" in recipe
    assert recipe["title"] == sample_recipe_data["title"]
    
    # Get recipe
    get_response = client.get(f"/api/recipes/{recipe['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == recipe["id"]


def test_recipe_not_found(client, clean_storage):
    """Contract test: Non-existent recipe returns 404"""
    response = client.get("/api/recipes/non-existent-id")
    assert response.status_code == 404


def test_recipe_pages_load(client, clean_storage, sample_recipe_data):
    """Smoke test: Recipe HTML pages load without error"""
    # Create a recipe first
    create_response = client.post("/api/recipes", json=sample_recipe_data)
    recipe_id = create_response.json()["id"]

    # Test recipe detail page
    response = client.get(f"/recipes/{recipe_id}")
    assert response.status_code == 200

    # Test new recipe form
    response = client.get("/recipes/new")
    assert response.status_code == 200

    # Test import page
    response = client.get("/import")
    assert response.status_code == 200


# --- GET /api/recipes ---


def test_get_recipes_with_search(client, clean_storage, sample_recipe_data):
    """Contract test: GET /api/recipes?search= returns filtered list"""
    client.post("/api/recipes", json=sample_recipe_data)
    response = client.get("/api/recipes", params={"search": "Test"})
    assert response.status_code == 200
    data = response.json()
    assert "recipes" in data
    assert len(data["recipes"]) >= 1
    assert all("Test" in r["title"] for r in data["recipes"])


# --- GET /api/recipes/export ---


def test_export_recipes(client, clean_storage, sample_recipe_data):
    """Contract test: GET /api/recipes/export returns JSON array"""
    client.post("/api/recipes", json=sample_recipe_data)
    response = client.get("/api/recipes/export")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "id" in data[0]
    assert "title" in data[0]


# --- PUT /api/recipes/{id} ---


def test_update_recipe_success(client, clean_storage, sample_recipe_data):
    """Contract test: PUT /api/recipes/{id} updates recipe"""
    create_resp = client.post("/api/recipes", json=sample_recipe_data)
    recipe_id = create_resp.json()["id"]
    update_data = {**sample_recipe_data, "title": "Updated Title"}
    response = client.put(f"/api/recipes/{recipe_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


def test_update_recipe_not_found(client, clean_storage, sample_recipe_data):
    """Contract test: PUT /api/recipes/{id} returns 404 for missing recipe"""
    update_data = {**sample_recipe_data, "title": "Updated"}
    response = client.put("/api/recipes/non-existent-id", json=update_data)
    assert response.status_code == 404
    assert "detail" in response.json()


# --- DELETE /api/recipes/{id} ---


def test_delete_recipe_success(client, clean_storage, sample_recipe_data):
    """Contract test: DELETE /api/recipes/{id} returns 200 and removes recipe"""
    create_resp = client.post("/api/recipes", json=sample_recipe_data)
    recipe_id = create_resp.json()["id"]
    response = client.delete(f"/api/recipes/{recipe_id}")
    assert response.status_code == 200
    data = response.json()
    assert data.get("message") == "Recipe deleted successfully"
    assert data.get("status") == "success"
    get_resp = client.get(f"/api/recipes/{recipe_id}")
    assert get_resp.status_code == 404


def test_delete_recipe_not_found(client, clean_storage):
    """Contract test: DELETE /api/recipes/{id} returns 404 for missing recipe"""
    response = client.delete("/api/recipes/non-existent-id")
    assert response.status_code == 404
    assert "detail" in response.json()


# --- POST /api/recipes validation (422) ---


def test_create_recipe_422_empty_title(client, clean_storage, sample_recipe_data):
    """Contract test: POST /api/recipes returns 422 for empty title"""
    bad_data = {**sample_recipe_data, "title": ""}
    response = client.post("/api/recipes", json=bad_data)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_recipe_422_empty_ingredients(client, clean_storage, sample_recipe_data):
    """Contract test: POST /api/recipes returns 422 for no ingredients"""
    bad_data = {**sample_recipe_data, "ingredients": []}
    response = client.post("/api/recipes", json=bad_data)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_recipe_422_empty_instructions(client, clean_storage, sample_recipe_data):
    """Contract test: POST /api/recipes returns 422 for no instructions"""
    bad_data = {**sample_recipe_data, "instructions": []}
    response = client.post("/api/recipes", json=bad_data)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_recipe_422_title_too_long(client, clean_storage, sample_recipe_data):
    """Contract test: POST /api/recipes returns 422 for title over 200 chars"""
    bad_data = {**sample_recipe_data, "title": "x" * 201}
    response = client.post("/api/recipes", json=bad_data)
    assert response.status_code == 422
    assert "detail" in response.json()


# --- POST /api/recipes/import ---


def test_import_recipes_success(client, clean_storage, valid_import_json):
    """Contract test: POST /api/recipes/import with valid JSON returns 200"""
    content = json.dumps(valid_import_json).encode("utf-8")
    response = client.post(
        "/api/recipes/import",
        files={"file": ("recipes.json", io.BytesIO(content), "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert data["count"] == 1
    assert "message" in data


def test_import_recipes_400_invalid_json(client, clean_storage):
    """Contract test: POST /api/recipes/import returns 400 for invalid JSON"""
    content = b"not valid json {"
    response = client.post(
        "/api/recipes/import",
        files={"file": ("recipes.json", io.BytesIO(content), "application/json")},
    )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_import_recipes_400_not_array(client, clean_storage):
    """Contract test: POST /api/recipes/import returns 400 when root is not array"""
    content = b'{"title": "single recipe"}'
    response = client.post(
        "/api/recipes/import",
        files={"file": ("recipes.json", io.BytesIO(content), "application/json")},
    )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_import_recipes_400_file_too_large(client, clean_storage, valid_import_json):
    """Contract test: POST /api/recipes/import returns 400 for file > 1MB"""
    # Create payload > 1MB
    huge = valid_import_json * 50000  # ~several MB
    content = json.dumps(huge).encode("utf-8")
    response = client.post(
        "/api/recipes/import",
        files={"file": ("recipes.json", io.BytesIO(content), "application/json")},
    )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_import_recipes_422_schema_validation(client, clean_storage):
    """Contract test: POST /api/recipes/import returns 422 for invalid recipe schema"""
    invalid_recipes = [
        {
            "id": "bad-001",
            "title": "Valid title",
            "description": "Valid desc",
            "ingredients": [],  # Invalid: must have at least one
            "instructions": ["Step 1"],
            "tags": [],
            "cuisine": None,
        }
    ]
    content = json.dumps(invalid_recipes).encode("utf-8")
    response = client.post(
        "/api/recipes/import",
        files={"file": ("recipes.json", io.BytesIO(content), "application/json")},
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    detail = data["detail"]
    assert "errors" in detail
    assert len(detail["errors"]) > 0
