"""
Prometheus metrics for cache performance, API usage, and recipe popularity.
Exposed via /metrics endpoint for Prometheus scraping.
"""

from prometheus_client import Counter, Histogram

# Cache metrics (Redis)
cache_hits_total = Counter(
    "recipe_explorer_cache_hits_total",
    "Total cache hits (Redis)",
    ["operation"],  # search, meal
)
cache_misses_total = Counter(
    "recipe_explorer_cache_misses_total",
    "Total cache misses (Redis)",
    ["operation"],
)

# Response time histograms (seconds)
internal_query_duration_seconds = Histogram(
    "recipe_explorer_internal_query_duration_seconds",
    "Internal storage query duration in seconds",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
external_query_duration_seconds = Histogram(
    "recipe_explorer_external_query_duration_seconds",
    "External API query duration in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0),
)

# Recipe popularity (search frequency)
recipe_search_total = Counter(
    "recipe_explorer_search_total",
    "Recipe search requests by query",
    ["query"],
)

# MealDB API success/failure
mealdb_api_calls_total = Counter(
    "recipe_explorer_mealdb_api_calls_total",
    "MealDB API calls by status",
    ["operation", "status"],  # search/meal, success/failure
)


def record_cache_hit(operation: str) -> None:
    """Record a cache hit for the given operation (search or meal)."""
    cache_hits_total.labels(operation=operation).inc()


def record_cache_miss(operation: str) -> None:
    """Record a cache miss for the given operation."""
    cache_misses_total.labels(operation=operation).inc()


def record_internal_duration(seconds: float) -> None:
    """Record internal query duration."""
    internal_query_duration_seconds.observe(seconds)


def record_external_duration(seconds: float) -> None:
    """Record external API query duration."""
    external_query_duration_seconds.observe(seconds)


def record_recipe_search(query: str) -> None:
    """Record a recipe search (for popularity tracking). Normalizes query for cardinality."""
    normalized = query.strip().lower()[:100] if query else "empty"
    recipe_search_total.labels(query=normalized).inc()


def record_mealdb_api(operation: str, success: bool) -> None:
    """Record MealDB API call result."""
    status = "success" if success else "failure"
    mealdb_api_calls_total.labels(operation=operation, status=status).inc()
