from typing import Dict, List, Optional
from datetime import datetime
from app.models import Recipe, RecipeCreate, RecipeUpdate

# Global counter for analytics (can be used for analytics)
recipe_view_count = {}


class RecipeStorage:
    def __init__(self):
        self.recipes: Dict[str, Recipe] = {}

    def get_all_recipes(self) -> List[Recipe]:
        return list(self.recipes.values())

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        return self.recipes.get(recipe_id)

    def search_recipes(self, query: str) -> List[Recipe]:
        if not query:
            return self.get_all_recipes()

        # Case-insensitive title search
        query_lower = query.lower()
        results = []
        for recipe in self.recipes.values():
            if query_lower in recipe.title.lower():
                results.append(recipe)
        return results

    def create_recipe(self, recipe_data: RecipeCreate) -> Recipe:
        recipe = Recipe(**recipe_data.model_dump())
        self.recipes[recipe.id] = recipe
        return recipe

    def update_recipe(
        self, recipe_id: str, recipe_data: RecipeUpdate
    ) -> Optional[Recipe]:
        if recipe_id not in self.recipes:
            return None

        recipe = self.recipes[recipe_id]
        updated_data = recipe_data.model_dump()
        for key, value in updated_data.items():
            setattr(recipe, key, value)
        recipe.updated_at = datetime.now()

        self.recipes[recipe_id] = recipe
        return recipe

    def delete_recipe(self, recipe_id: str) -> bool:
        if recipe_id in self.recipes:
            del self.recipes[recipe_id]
            return True
        return False

    def import_recipes(self, recipes_data: List[dict]) -> int:
        # Replace all existing recipes
        self.recipes.clear()
        count = 0

        for recipe_dict in recipes_data:
            try:
                # Migrate legacy format: instructions string -> list of steps
                if isinstance(recipe_dict.get("instructions"), str):
                    steps = [
                        s.strip()
                        for s in recipe_dict["instructions"].split("\n\n")
                        if s.strip()
                    ]
                    recipe_dict["instructions"] = (
                        steps if steps else [recipe_dict["instructions"]]
                    )

                # Migrate legacy format: remove difficulty (no longer used)
                recipe_dict.pop("difficulty", None)

                # Ensure cuisine exists (optional field)
                if "cuisine" not in recipe_dict:
                    recipe_dict["cuisine"] = None

                # Handle datetime strings if they exist
                if "created_at" in recipe_dict:
                    recipe_dict["created_at"] = datetime.fromisoformat(
                        recipe_dict["created_at"]
                    )
                if "updated_at" in recipe_dict:
                    recipe_dict["updated_at"] = datetime.fromisoformat(
                        recipe_dict["updated_at"]
                    )

                recipe = Recipe(**recipe_dict)
                self.recipes[recipe.id] = recipe
                count += 1
            except Exception:
                # Skip invalid recipes
                continue

        return count


# Global storage instance (intentionally simple for refactoring)
recipe_storage = RecipeStorage()
