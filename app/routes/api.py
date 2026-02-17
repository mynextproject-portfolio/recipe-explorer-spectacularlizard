import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from app.core.abstractions import ExternalRecipeSource, RecipeRepository
from app.core.dependencies import get_external_recipe_source, get_recipe_storage
from app.models import Recipe, RecipeCreate, RecipeUpdate
from app.services.metrics import (
    aggregate_metrics,
    current_metrics,
    start_request_metrics,
    timed_internal,
    timed_external,
)
from app.validation import validate_recipes_for_import

router = APIRouter(prefix="/api")


def _recipe_to_response(recipe: Recipe, source: str = "internal") -> dict[str, Any]:
    """Convert Recipe to API response dict with source field."""
    data = recipe.model_dump(mode="json")
    data["source"] = source
    return data


def _build_response(data: dict, include_metrics: bool = True) -> dict:
    """Build response dict, optionally including timing metrics."""
    if include_metrics:
        m = current_metrics()
        if m is not None:
            metrics_dict = m.to_dict()
            aggregate_metrics.record(
                m.internal_ms,
                m.external_ms,
                cache_hits=m.cache_hits,
                cache_misses=m.cache_misses,
            )
            data = {**data, "_metrics": metrics_dict}
    return data


@router.get("/recipes")
def get_recipes(
    search: Optional[str] = None,
    storage: RecipeRepository = Depends(get_recipe_storage),
    external: ExternalRecipeSource = Depends(get_external_recipe_source),
):
    """Get all recipes or search by title. Combines internal and external sources when searching."""
    start_request_metrics()
    # TODO: Add pagination when we have more than 100 recipes
    if search:
        with timed_internal():
            internal_recipes = storage.search_recipes(search)
        with timed_external():
            external_recipes = external.search_meals(search)
        internal_with_source = [
            _recipe_to_response(r, "internal") for r in internal_recipes
        ]
        combined = internal_with_source + external_recipes
    else:
        with timed_internal():
            internal_recipes = storage.get_all_recipes()
        combined = [_recipe_to_response(r, "internal") for r in internal_recipes]

    return _build_response({"recipes": combined})


@router.get("/recipes/search")
def search_recipes(
    q: Optional[str] = None,
    storage: RecipeRepository = Depends(get_recipe_storage),
    external: ExternalRecipeSource = Depends(get_external_recipe_source),
):
    """Search recipes by query. Accepts 'q' as query parameter. Returns combined internal + external results."""
    start_request_metrics()
    if q:
        with timed_internal():
            internal_recipes = storage.search_recipes(q)
        with timed_external():
            external_recipes = external.search_meals(q)
        internal_with_source = [
            _recipe_to_response(r, "internal") for r in internal_recipes
        ]
        combined = internal_with_source + external_recipes
    else:
        with timed_internal():
            internal_recipes = storage.get_all_recipes()
        combined = [_recipe_to_response(r, "internal") for r in internal_recipes]
    return _build_response({"recipes": combined})


@router.get("/recipes/internal/{recipe_id}")
def get_recipe_internal(
    recipe_id: str,
    storage: RecipeRepository = Depends(get_recipe_storage),
):
    """Get a recipe by ID from internal storage."""
    start_request_metrics()
    with timed_internal():
        recipe = storage.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _build_response(_recipe_to_response(recipe, "internal"))


@router.get("/recipes/external/{recipe_id}")
def get_recipe_external(
    recipe_id: str,
    external: ExternalRecipeSource = Depends(get_external_recipe_source),
):
    """Get a recipe by ID from TheMealDB (external). Use numeric meal ID (e.g. 52772)."""
    start_request_metrics()
    with timed_external():
        recipe_dict = external.get_meal_by_id(recipe_id)
    if not recipe_dict:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _build_response(recipe_dict)


@router.get("/recipes/export")
def export_recipes(
    storage: RecipeRepository = Depends(get_recipe_storage),
):
    """Export all recipes as JSON"""
    recipes = storage.get_all_recipes()
    recipes_dict = [recipe.model_dump(mode="json") for recipe in recipes]
    return JSONResponse(content=recipes_dict)


@router.get("/recipes/{recipe_id}")
def get_recipe(
    recipe_id: str,
    storage: RecipeRepository = Depends(get_recipe_storage),
    external: ExternalRecipeSource = Depends(get_external_recipe_source),
):
    """Get a recipe by ID from internal or external source."""
    start_request_metrics()
    with timed_internal():
        recipe = storage.get_recipe(recipe_id)
    if recipe:
        return _build_response(_recipe_to_response(recipe, "internal"))

    # Try external (numeric ID or external-{id} format)
    external_id = recipe_id
    if recipe_id.startswith("external-"):
        external_id = recipe_id.replace("external-", "", 1)
    with timed_external():
        recipe_dict = external.get_meal_by_id(external_id)
    if recipe_dict:
        return _build_response(recipe_dict)

    raise HTTPException(status_code=404, detail="Recipe not found")


@router.post("/recipes")
def create_recipe(
    recipe: RecipeCreate,
    storage: RecipeRepository = Depends(get_recipe_storage),
):
    """Create a new recipe"""
    new_recipe = storage.create_recipe(recipe)
    return new_recipe


@router.put("/recipes/{recipe_id}")
def update_recipe(
    recipe_id: str,
    recipe: RecipeUpdate,
    storage: RecipeRepository = Depends(get_recipe_storage),
):
    """Update an existing recipe"""
    updated_recipe = storage.update_recipe(recipe_id, recipe)
    if not updated_recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return updated_recipe


@router.delete("/recipes/{recipe_id}")
def delete_recipe(
    recipe_id: str,
    storage: RecipeRepository = Depends(get_recipe_storage),
):
    """Delete a recipe"""
    success = storage.delete_recipe(recipe_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"message": "Recipe deleted successfully", "status": "success"}


@router.post("/recipes/import")
async def import_recipes(
    file: UploadFile = File(...),
    storage: RecipeRepository = Depends(get_recipe_storage),
):
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
    count = storage.import_recipes(recipes_dict)

    return {"message": f"Successfully imported {count} recipes", "count": count}


@router.get("/metrics")
def get_metrics():
    """Return aggregate performance metrics (internal vs external query times)."""
    return aggregate_metrics.to_dict()
