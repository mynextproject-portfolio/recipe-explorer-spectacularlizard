"""
Recipe validation utilities for schema compliance.

Used by the API import endpoint and the validate_recipes CLI script.
"""

from datetime import datetime

from pydantic import ValidationError

from app.models import Recipe


def migrate_legacy_recipe_format(recipe_dict: dict) -> dict:
    """Normalize legacy recipe formats for validation."""
    data = dict(recipe_dict)

    # Migrate instructions: string -> list
    if isinstance(data.get("instructions"), str):
        steps = [
            s.strip()
            for s in data["instructions"].split("\n\n")
            if s.strip()
        ]
        data["instructions"] = steps if steps else [data["instructions"]]

    # Remove obsolete fields
    data.pop("difficulty", None)

    # Ensure optional fields
    if "cuisine" not in data:
        data["cuisine"] = None
    if "tags" not in data:
        data["tags"] = []

    # Parse datetime strings
    if "created_at" in data and isinstance(data["created_at"], str):
        data["created_at"] = datetime.fromisoformat(data["created_at"])
    if "updated_at" in data and isinstance(data["updated_at"], str):
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])

    return data


def validate_recipe_for_import(recipe_dict: dict) -> tuple[Recipe | None, list[dict]]:
    """
    Validate a single recipe dict for import.

    Returns:
        Tuple of (Recipe instance or None, list of error dicts for 422 response).
    """
    if not isinstance(recipe_dict, dict):
        return None, [
            {
                "loc": ("body",),
                "msg": f"Each item must be an object, got {type(recipe_dict).__name__}",
                "type": "type_error",
            }
        ]

    try:
        migrated = migrate_legacy_recipe_format(recipe_dict)
        recipe = Recipe(**migrated)
        return recipe, []
    except ValidationError as e:
        errors = []
        for err in e.errors():
            errors.append(
                {
                    "loc": ("body",) + tuple(err["loc"]),
                    "msg": err["msg"],
                    "type": err.get("type", "value_error"),
                }
            )
        return None, errors


def validate_recipes_for_import(
    recipes_data: list,
) -> tuple[list[Recipe], list[dict]]:
    """
    Validate all recipes for import. Collects all validation errors.

    Returns:
        Tuple of (valid_recipes, all_errors).
        If any validation errors exist, valid_recipes may still contain some valid items
        but the caller should typically reject the entire import with 422.
    """
    valid: list[Recipe] = []
    all_errors: list[dict] = []

    for i, item in enumerate(recipes_data):
        recipe, errs = validate_recipe_for_import(item)
        if errs:
            for e in errs:
                err_copy = dict(e)
                err_copy["index"] = i
                err_copy["recipe_id"] = item.get("id", "?") if isinstance(item, dict) else "?"
                err_copy["recipe_title"] = item.get("title", "<no title>") if isinstance(item, dict) else "<no title>"
                all_errors.append(err_copy)
        elif recipe:
            valid.append(recipe)

    return valid, all_errors
