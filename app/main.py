import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routes import api, pages
import os
from app.services.storage import recipe_storage

# App configuration
APP_NAME = "Recipe Explorer"
VERSION = "1.0.0"
DEBUG = True

SAMPLE_DATA_PATH = Path(__file__).parent.parent / "sample-recipes.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load sample recipes during application startup."""
    if not SAMPLE_DATA_PATH.exists():
        print(f"No sample data file found at {SAMPLE_DATA_PATH}")
    else:
        try:
            with open(SAMPLE_DATA_PATH, "r", encoding="utf-8") as sample_file:
                recipes_data = json.load(sample_file)
            count = recipe_storage.import_recipes(recipes_data)
            print(f"Seeded {count} recipes from {SAMPLE_DATA_PATH.name}")
        except Exception as error:
            print(f"Failed to seed sample data: {error}")

    yield


# Create FastAPI app
app = FastAPI(title=APP_NAME, version=VERSION, lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(api.router)
app.include_router(pages.router)


# Basic health check
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# @app.get("/status")
# def status():
#     return {"status": "ok", "version": "1.0.0"}
