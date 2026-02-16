from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Any, List, Optional

from app.models import RecipeCreate, RecipeUpdate
from app.services.storage import recipe_storage
from app.adapters.themealdb import themealdb_adapter

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_combined_recipes(search: Optional[str] = None) -> List[dict[str, Any]]:
    """Get recipes from internal and external sources, with source field."""
    if search:
        internal = recipe_storage.search_recipes(search)
        external = themealdb_adapter.search_meals(search)
    else:
        internal = recipe_storage.get_all_recipes()
        external = []

    result = []
    for r in internal:
        data = r.model_dump(mode="json")
        data["source"] = "internal"
        result.append(data)
    result.extend(external)
    return result


def _get_recipe_for_detail(recipe_id: str) -> Optional[dict[str, Any]]:
    """Get recipe by ID from internal or external source."""
    # Try internal first
    recipe = recipe_storage.get_recipe(recipe_id)
    if recipe:
        data = recipe.model_dump(mode="json")
        data["source"] = "internal"
        return data

    # Try external
    external_id = recipe_id.replace("external-", "", 1) if recipe_id.startswith("external-") else recipe_id
    return themealdb_adapter.get_meal_by_id(external_id)


@router.get("/", response_class=HTMLResponse)
def home(request: Request, search: Optional[str] = None, message: Optional[str] = None):
    """Home page with recipe list and search (combined internal + external)"""
    recipes = _get_combined_recipes(search)

    return templates.TemplateResponse(request, "index.html", {
        "recipes": recipes,
        "search_query": search or "",
        "message": message
    })


@router.get("/recipes/new", response_class=HTMLResponse)
def new_recipe_form(request: Request):
    """New recipe form"""
    return templates.TemplateResponse(request, "recipe_form.html", {
        "recipe": None,
        "is_edit": False
    })


@router.get("/recipes/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(request: Request, recipe_id: str, message: Optional[str] = None):
    """Recipe detail page (internal or external)"""
    recipe = _get_recipe_for_detail(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Pass as dict so template can check source and show/hide Edit/Delete
    return templates.TemplateResponse(request, "recipe_detail.html", {
        "recipe": recipe,
        "message": message
    })


@router.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
def edit_recipe_form(request: Request, recipe_id: str):
    """Edit recipe form"""
    recipe = recipe_storage.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    return templates.TemplateResponse(request, "recipe_form.html", {
        "recipe": recipe,
        "is_edit": True
    })


@router.post("/recipes/new")
def create_recipe_form(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    ingredients: str = Form(...),
    instructions: str = Form(...),
    tags: str = Form(...),
    cuisine: Optional[str] = Form(default="")
):
    """Handle new recipe form submission"""
    try:
        # Check title length
        if len(title) > 200:
            raise ValueError("Title too long")

        # Parse ingredients (one per line) and tags (comma-separated)
        ingredient_list = [ing.strip() for ing in ingredients.split('\n') if ing.strip()]
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]

        # Parse instructions: one step per line
        step_list = [s.strip() for s in instructions.split('\n') if s.strip()]

        # Validation
        if len(ingredient_list) == 0:
            raise ValueError("At least one ingredient required")

        if len(step_list) == 0:
            raise ValueError("Instructions are required")

        recipe_data = RecipeCreate(
            title=title,
            description=description,
            ingredients=ingredient_list,
            instructions=step_list,
            tags=tag_list,
            cuisine=cuisine.strip() or None
        )
        
        new_recipe = recipe_storage.create_recipe(recipe_data)
        return RedirectResponse(
            url=f"/recipes/{new_recipe.id}?message=Recipe created successfully",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/?message=Error creating recipe: {str(e)}",
            status_code=303
        )


@router.post("/recipes/{recipe_id}/edit")
def update_recipe_form(
    request: Request,
    recipe_id: str,
    title: str = Form(...),
    description: str = Form(...),
    ingredients: str = Form(...),
    instructions: str = Form(...),
    tags: str = Form(...),
    cuisine: Optional[str] = Form(default="")
):
    """Handle edit recipe form submission"""
    try:
        # Check title length
        if len(title) > 200:
            raise ValueError("Title is too long!")

        # Parse ingredients (one per line) and tags (comma-separated)
        ingredient_list = [ing.strip() for ing in ingredients.split('\n') if ing.strip()]
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]

        # Parse instructions: one step per line
        step_list = [s.strip() for s in instructions.split('\n') if s.strip()]

        if len(ingredient_list) == 0:
            raise ValueError("Need ingredients!")

        if len(step_list) == 0:
            raise ValueError("Instructions are required")

        recipe_data = RecipeUpdate(
            title=title,
            description=description,
            ingredients=ingredient_list,
            instructions=step_list,
            tags=tag_list,
            cuisine=cuisine.strip() or None
        )
        
        updated_recipe = recipe_storage.update_recipe(recipe_id, recipe_data)
        if not updated_recipe:
            return RedirectResponse(
                url=f"/?message=Recipe not found",
                status_code=303
            )
        
        return RedirectResponse(
            url=f"/recipes/{recipe_id}?message=Recipe updated successfully",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/recipes/{recipe_id}?message=Error updating recipe: {str(e)}",
            status_code=303
        )


@router.post("/recipes/{recipe_id}/delete")
def delete_recipe_form(recipe_id: str):
    """Handle recipe deletion"""
    success = recipe_storage.delete_recipe(recipe_id)
    if success:
        return RedirectResponse(
            url="/?message=Recipe deleted successfully",
            status_code=303
        )
    else:
        return RedirectResponse(
            url="/?message=Recipe not found",
            status_code=303
        )


@router.get("/import", response_class=HTMLResponse)
def import_page(request: Request, message: Optional[str] = None):
    """Import recipes page"""
    return templates.TemplateResponse(request, "import.html", {
        "message": message
    })
