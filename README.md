# Recipe Explorer

A simple FastAPI web application for managing recipes. Features CRUD operations, search, file uploads, and a Bootstrap frontend.

**Tech Stack:** FastAPI, Jinja2, Bootstrap 5, pytest

## Quick Start

### Run Locally

```bash
# Clone and setup
git clone <repository-url>
cd recipe-explorer-template
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install and run
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit **http://localhost:8000**

### Run with Docker

```bash
docker build -t recipe-explorer .
docker run -p 8000:8000 recipe-explorer
```

Visit **http://localhost:8000**

### Run with Docker Compose (Redis caching + Prometheus)

MealDB API responses are cached in Redis (24h TTL) for improved search performance. Prometheus collects metrics for cache performance, API usage, and recipe popularity:

```bash
docker compose up
```

- **App:** http://localhost:8000
- **Prometheus UI:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin / admin)
- **Metrics endpoint:** http://localhost:8000/metrics (Prometheus format)

Use `GET /api/metrics` for JSON aggregate metrics or `/metrics` for Prometheus scraping. Grafana is pre-configured with Prometheus as a datasource—add dashboards to visualize cache hit rate, API latency, and recipe search popularity.

## Sample Data

Upload the `sample-recipes.json` file using the "Import Recipes" page to get started with 3 example recipes (Poutine, Shuba, Guo Bao Rou).

## Testing

```bash
pytest           # Run all tests
pytest -v        # Verbose output
```

## Schema Validation

Validate recipe JSON files against the schema before importing:

```bash
python scripts/validate_recipes.py sample-recipes.json
python scripts/validate_recipes.py path/to/recipes.json
```

Exit code 0 = valid, 1 = validation failed.

## API Endpoints

**Pages:**
- `/` - Home page with recipe list
- `/recipes/new` - Add recipe form  
- `/recipes/{id}` - Recipe detail page
- `/import` - Import recipes

**API:**
- `GET /api/recipes` - List/search recipes
- `POST /api/recipes` - Create recipe
- `GET /api/recipes/{id}` - Get recipe
- `GET /api/metrics` - Performance metrics (JSON, internal/external query times, cache hits)
- `GET /metrics` - Prometheus metrics (cache hit/miss, response times, recipe popularity, MealDB API success/failure)
- `PUT /api/recipes/{id}` - Update recipe
- `DELETE /api/recipes/{id}` - Delete recipe
- `POST /api/recipes/import` - Import JSON
- `GET /api/recipes/export` - Export JSON

---

*Part of [mynextproject.dev](https://mynextproject.dev) - Learn to code like a professional*
