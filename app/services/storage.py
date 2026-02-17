"""
Recipe storage implementations.
SQLite-backed persistence with in-memory support for testing.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.models import Recipe, RecipeCreate, RecipeUpdate

# Global counter for analytics (can be used for analytics)
recipe_view_count: Dict[str, int] = {}


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create recipes table if not exists."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            instructions TEXT NOT NULL,
            tags TEXT NOT NULL,
            cuisine TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()


def _recipe_from_row(row: tuple) -> Recipe:
    """Build Recipe from DB row."""
    (
        id_,
        title,
        description,
        ingredients_json,
        instructions_json,
        tags_json,
        cuisine,
        created_at,
        updated_at,
    ) = row
    return Recipe(
        id=id_,
        title=title,
        description=description,
        ingredients=json.loads(ingredients_json),
        instructions=json.loads(instructions_json),
        tags=json.loads(tags_json),
        cuisine=cuisine,
        created_at=datetime.fromisoformat(created_at),
        updated_at=datetime.fromisoformat(updated_at),
    )


def _recipe_to_row(recipe: Recipe) -> tuple:
    """Convert Recipe to DB row tuple."""
    return (
        recipe.id,
        recipe.title,
        recipe.description,
        json.dumps(recipe.ingredients),
        json.dumps(recipe.instructions),
        json.dumps(recipe.tags),
        recipe.cuisine,
        recipe.created_at.isoformat(),
        recipe.updated_at.isoformat(),
    )


class _ClearableRecipesProxy:
    """Proxy exposing clear() for test fixture compatibility (storage.recipes.clear())."""

    def __init__(self, storage: "RecipeStorage") -> None:
        self._storage = storage

    def clear(self) -> None:
        self._storage._clear_all()


class RecipeStorage:
    """SQLite-backed recipe storage implementing RecipeRepository."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or ":memory:"
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        _init_schema(self._conn)
        self.recipes = _ClearableRecipesProxy(self)

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def _clear_all(self) -> None:
        """Clear all recipes. Used by tests via recipes.clear()."""
        self._conn.execute("DELETE FROM recipes")
        self._conn.commit()

    def get_all_recipes(self) -> List[Recipe]:
        cur = self._conn.execute(
            "SELECT id, title, description, ingredients, instructions, tags, "
            "cuisine, created_at, updated_at FROM recipes"
        )
        return [_recipe_from_row(tuple(r)) for r in cur.fetchall()]

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        cur = self._conn.execute(
            "SELECT id, title, description, ingredients, instructions, tags, "
            "cuisine, created_at, updated_at FROM recipes WHERE id = ?",
            (recipe_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return _recipe_from_row(tuple(row))

    def search_recipes(self, query: str) -> List[Recipe]:
        if not query:
            return self.get_all_recipes()
        query_lower = query.lower()
        results = []
        for recipe in self.get_all_recipes():
            if query_lower in recipe.title.lower():
                results.append(recipe)
        return results

    def create_recipe(self, recipe_data: RecipeCreate) -> Recipe:
        recipe = Recipe(**recipe_data.model_dump())
        self._conn.execute(
            "INSERT INTO recipes (id, title, description, ingredients, instructions, "
            "tags, cuisine, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _recipe_to_row(recipe),
        )
        self._conn.commit()
        return recipe

    def update_recipe(
        self, recipe_id: str, recipe_data: RecipeUpdate
    ) -> Optional[Recipe]:
        existing = self.get_recipe(recipe_id)
        if existing is None:
            return None
        updated_data = recipe_data.model_dump()
        recipe_dict = existing.model_dump()
        recipe_dict.update(updated_data)
        recipe_dict["updated_at"] = datetime.now()
        recipe = Recipe(**recipe_dict)
        self._conn.execute(
            "UPDATE recipes SET title=?, description=?, ingredients=?, instructions=?, "
            "tags=?, cuisine=?, updated_at=? WHERE id=?",
            (
                recipe.title,
                recipe.description,
                json.dumps(recipe.ingredients),
                json.dumps(recipe.instructions),
                json.dumps(recipe.tags),
                recipe.cuisine,
                recipe.updated_at.isoformat(),
                recipe_id,
            ),
        )
        self._conn.commit()
        return recipe

    def delete_recipe(self, recipe_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def import_recipes(self, recipes_data: List[dict]) -> int:
        self._clear_all()
        count = 0

        for recipe_dict in recipes_data:
            try:
                if isinstance(recipe_dict.get("instructions"), str):
                    steps = [
                        s.strip()
                        for s in recipe_dict["instructions"].split("\n\n")
                        if s.strip()
                    ]
                    recipe_dict["instructions"] = (
                        steps if steps else [recipe_dict["instructions"]]
                    )

                recipe_dict.pop("difficulty", None)

                if "cuisine" not in recipe_dict:
                    recipe_dict["cuisine"] = None

                if "created_at" in recipe_dict:
                    recipe_dict["created_at"] = datetime.fromisoformat(
                        recipe_dict["created_at"]
                    )
                if "updated_at" in recipe_dict:
                    recipe_dict["updated_at"] = datetime.fromisoformat(
                        recipe_dict["updated_at"]
                    )

                recipe = Recipe(**recipe_dict)
                self._conn.execute(
                    "INSERT INTO recipes (id, title, description, ingredients, "
                    "instructions, tags, cuisine, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    _recipe_to_row(recipe),
                )
                count += 1
            except Exception:
                continue

        self._conn.commit()
        return count


# Global storage instance (backwards compatibility; prefer get_recipe_storage)
recipe_storage = RecipeStorage(db_path=None)
