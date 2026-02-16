from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List, Optional
import json

from app.models import Recipe, RecipeCreate, RecipeUpdate
from app.services.storage import recipe_storage
from app.validation import validate_recipes_for_import

router = APIRouter(prefix="/api")


@router.get("/recipes")
def get_recipes(search: Optional[str] = None):
    """Get all recipes or search by title"""
    # TODO: Add pagination when we have more than 100 recipes
    if search:
        recipes = recipe_storage.search_recipes(search)
    else:
        recipes = recipe_storage.get_all_recipes()

    # Log for debugging (remove in production)
    print(f"Returning {len(recipes)} recipes")

    return {"recipes": recipes}


@router.get("/recipes/export")
def export_recipes():
    """Export all recipes as JSON"""
    recipes = recipe_storage.get_all_recipes()
    recipes_dict = [recipe.model_dump(mode="json") for recipe in recipes]
    return JSONResponse(content=recipes_dict)


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: str):
    """Get a specific recipe by ID"""
    recipe = recipe_storage.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


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
