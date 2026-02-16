from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from typing import Any, List, Optional
import json

from app.models import Recipe, RecipeCreate, RecipeUpdate
from app.services.storage import recipe_storage
from app.validation import validate_recipes_for_import
from app.adapters.themealdb import themealdb_adapter

router = APIRouter(prefix="/api")


def _recipe_to_response(recipe: Recipe, source: str = "internal") -> dict[str, Any]:
    """Convert Recipe to API response dict with source field."""
    data = recipe.model_dump(mode="json")
    data["source"] = source
    return data


@router.get("/recipes")
def get_recipes(search: Optional[str] = None):
    """Get all recipes or search by title. Combines internal and external sources when searching."""
    # TODO: Add pagination when we have more than 100 recipes
    if search:
        internal_recipes = recipe_storage.search_recipes(search)
        external_recipes = themealdb_adapter.search_meals(search)
        internal_with_source = [_recipe_to_response(r, "internal") for r in internal_recipes]
        combined = internal_with_source + external_recipes
    else:
        internal_recipes = recipe_storage.get_all_recipes()
        combined = [_recipe_to_response(r, "internal") for r in internal_recipes]

    return {"recipes": combined}


@router.get("/recipes/internal/{recipe_id}")
def get_recipe_internal(recipe_id: str):
    """Get a recipe by ID from internal storage."""
    recipe = recipe_storage.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _recipe_to_response(recipe, "internal")


@router.get("/recipes/external/{recipe_id}")
def get_recipe_external(recipe_id: str):
    """Get a recipe by ID from TheMealDB (external). Use numeric meal ID (e.g. 52772)."""
    recipe_dict = themealdb_adapter.get_meal_by_id(recipe_id)
    if not recipe_dict:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe_dict


@router.get("/recipes/export")
def export_recipes():
    """Export all recipes as JSON"""
    recipes = recipe_storage.get_all_recipes()
    recipes_dict = [recipe.model_dump(mode="json") for recipe in recipes]
    return JSONResponse(content=recipes_dict)


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: str):
    """Get a recipe by ID from internal or external source."""
    # Try internal first
    recipe = recipe_storage.get_recipe(recipe_id)
    if recipe:
        return _recipe_to_response(recipe, "internal")

    # Try external (numeric ID or external-{id} format)
    external_id = recipe_id
    if recipe_id.startswith("external-"):
        external_id = recipe_id.replace("external-", "", 1)
    recipe_dict = themealdb_adapter.get_meal_by_id(external_id)
    if recipe_dict:
        return recipe_dict

    raise HTTPException(status_code=404, detail="Recipe not found")


@router.post("/recipes")
def create_recipe(recipe: RecipeCreate):
    """Create a new recipe"""
    new_recipe = recipe_storage.create_recipe(recipe)
    return new_recipe


@router.put("/recipes/{recipe_id}")
def update_recipe(recipe_id: str, recipe: RecipeUpdate):
    """Update an existing recipe"""
    updated_recipe = recipe_storage.update_recipe(recipe_id, recipe)
    if not updated_recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return updated_recipe


@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: str):
    """Delete a recipe"""
    success = recipe_storage.delete_recipe(recipe_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"message": "Recipe deleted successfully", "status": "success"}


@router.post("/recipes/import")
async def import_recipes(file: UploadFile = File(...)):
    """Import recipes from JSON file. Validates schema compliance before import."""
    # Read file
    content = await file.read()

    # 400: File too large
    if len(content) > 1_000_000:  # 1MB limit
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 1MB.",
        )

    # 400: Invalid JSON
    try:
        recipes_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON format: {e.msg} at line {e.lineno}",
        )

    # 400: Root must be array
    if not isinstance(recipes_data, list):
        raise HTTPException(
            status_code=400,
            detail="JSON must be an array of recipes.",
        )

    # 422: Schema validation - check all recipes before importing
    valid_recipes, validation_errors = validate_recipes_for_import(recipes_data)
    if validation_errors:
        errors_for_response = [
            {
                "index": e.get("index"),
                "recipe_id": e.get("recipe_id"),
                "recipe_title": e.get("recipe_title"),
                "loc": list(e.get("loc", [])),
                "msg": e.get("msg"),
                "type": e.get("type"),
            }
            for e in validation_errors
        ]
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Recipe schema validation failed",
                "errors": errors_for_response,
            },
        )

    # Import valid recipes (mode='json' for datetime serialization)
    recipes_dict = [r.model_dump(mode="json") for r in valid_recipes]
    count = recipe_storage.import_recipes(recipes_dict)

    return {"message": f"Successfully imported {count} recipes", "count": count}
