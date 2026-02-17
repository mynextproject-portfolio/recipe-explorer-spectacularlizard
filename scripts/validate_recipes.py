#!/usr/bin/env python3
"""
Validation script for recipe schema compliance.

Validates JSON files containing recipe data against the Recipe schema.
Use for CI checks, pre-import validation, or schema compliance testing.

Usage:
    python scripts/validate_recipes.py sample-recipes.json
    python scripts/validate_recipes.py path/to/recipes.json

Exit codes:
    0 - All recipes pass validation
    1 - Validation failed (schema errors or invalid JSON)
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.validation import validate_recipe_for_import


def validate_recipes_file(file_path: Path) -> tuple[list[dict], list[str]]:
    """
    Validate a JSON file against the Recipe schema.

    Returns:
        Tuple of (validation_errors, error_messages).
        validation_errors: list of error dicts with index, recipe_id/title, and Pydantic errors
        error_messages: human-readable messages for stdout
    """
    errors: list[dict] = []
    messages: list[str] = []

    if not file_path.exists():
        messages.append(f"Error: File not found: {file_path}")
        return [{"file": str(file_path), "error": "File not found"}], messages

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        messages.append(f"Error: Cannot read file: {e}")
        return [{"file": str(file_path), "error": str(e)}], messages

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        messages.append(f"Error: Invalid JSON at line {e.lineno}: {e.msg}")
        return [{"file": str(file_path), "error": f"Invalid JSON: {e.msg}"}], messages

    if not isinstance(data, list):
        messages.append("Error: Root must be a JSON array of recipes")
        return [{"file": str(file_path), "error": "Root must be an array"}], messages

    for i, item in enumerate(data):
        recipe, errs = validate_recipe_for_import(item)
        if errs:
            recipe_id = item.get("id", "?") if isinstance(item, dict) else "?"
            title = (
                item.get("title", "<no title>")
                if isinstance(item, dict)
                else "<no title>"
            )
            err_details = [f"  - {e.get('loc', '?')}: {e['msg']}" for e in errs]
            msg = (
                f"Recipe at index {i} (id={recipe_id}, title={title!r}):\n"
                + "\n".join(err_details)
            )
            messages.append(msg)
            errors.append(
                {
                    "index": i,
                    "id": recipe_id,
                    "title": title,
                    "errors": errs,
                }
            )

    return errors, messages


def main() -> int:
    """Run validation on given file(s)."""
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        print(
            "\nUsage: python scripts/validate_recipes.py <file.json> [file2.json ...]\n",
            file=sys.stderr,
        )
        return 1

    root = Path(__file__).resolve().parent.parent
    all_errors: list[dict] = []
    all_messages: list[str] = []

    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.is_absolute():
            path = root / path
        errs, msgs = validate_recipes_file(path)
        all_errors.extend(errs)
        all_messages.extend(msgs)

    for msg in all_messages:
        print(msg)

    if all_errors:
        print("\nValidation failed.", file=sys.stderr)
        return 1

    print("All recipes passed schema validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
