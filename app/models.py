from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
import uuid

# Schema constants for validation
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 10_000
MAX_INGREDIENTS = 50
MAX_INSTRUCTIONS = 100
MAX_TAGS = 20
MAX_CUISINE_LENGTH = 100


class Recipe(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(
        min_length=1, max_length=MAX_TITLE_LENGTH, description="Recipe title"
    )
    description: str = Field(
        min_length=1,
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Recipe description",
    )
    ingredients: List[str] = Field(
        min_length=1,
        max_length=MAX_INGREDIENTS,
        description="List of ingredients",
    )
    instructions: List[str] = Field(
        min_length=1,
        max_length=MAX_INSTRUCTIONS,
        description="Step-by-step instructions",
    )
    tags: List[str] = Field(
        default_factory=list, max_length=MAX_TAGS, description="Recipe tags"
    )
    cuisine: Optional[str] = Field(
        default=None, max_length=MAX_CUISINE_LENGTH, description="Cuisine type"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class RecipeCreate(BaseModel):
    title: str = Field(
        min_length=1, max_length=MAX_TITLE_LENGTH, description="Recipe title"
    )
    description: str = Field(
        min_length=1,
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Recipe description",
    )
    ingredients: List[str] = Field(
        min_length=1,
        max_length=MAX_INGREDIENTS,
        description="At least one ingredient required",
    )
    instructions: List[str] = Field(
        min_length=1,
        max_length=MAX_INSTRUCTIONS,
        description="Step-by-step instructions",
    )
    tags: List[str] = Field(
        default_factory=list, max_length=MAX_TAGS, description="Recipe tags"
    )
    cuisine: Optional[str] = Field(
        default=None, max_length=MAX_CUISINE_LENGTH, description="Cuisine type"
    )


class RecipeUpdate(BaseModel):
    title: str = Field(
        min_length=1, max_length=MAX_TITLE_LENGTH, description="Recipe title"
    )
    description: str = Field(
        min_length=1,
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Recipe description",
    )
    ingredients: List[str] = Field(
        min_length=1,
        max_length=MAX_INGREDIENTS,
        description="At least one ingredient required",
    )
    instructions: List[str] = Field(
        min_length=1,
        max_length=MAX_INSTRUCTIONS,
        description="Step-by-step instructions",
    )
    tags: List[str] = Field(max_length=MAX_TAGS, description="Recipe tags")
    cuisine: Optional[str] = Field(
        default=None, max_length=MAX_CUISINE_LENGTH, description="Cuisine type"
    )
