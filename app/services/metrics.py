"""
Performance metrics collection for internal vs external recipe queries.
Tracks response times for internal storage queries and external MealDB API calls.
Uses contextvars for request-scoped state (async-safe).
"""
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import ContextManager

logger = logging.getLogger(__name__)

# Request-scoped metrics (reset per request)
_request_metrics_var: ContextVar["RequestMetrics | None"] = ContextVar(
    "request_metrics", default=None
)


@dataclass
class RequestMetrics:
    """Metrics for a single request (internal and external timings)."""

    internal_ms: float = 0.0
    external_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "internal_ms": round(self.internal_ms, 2),
            "external_ms": round(self.external_ms, 2),
        }


def start_request_metrics() -> RequestMetrics:
    """Start tracking metrics for a new request. Call at the beginning of each API handler."""
    m = RequestMetrics()
    _request_metrics_var.set(m)
    return m


def current_metrics() -> RequestMetrics | None:
    """Return metrics for the current request, or None if not started."""
    return _request_metrics_var.get()


def record_internal(elapsed_ms: float) -> None:
    """Record an internal query duration."""
    m = _request_metrics_var.get()
    if m is not None:
        m.internal_ms += elapsed_ms


def record_external(elapsed_ms: float) -> None:
    """Record an external API call duration."""
    m = _request_metrics_var.get()
    if m is not None:
        m.external_ms += elapsed_ms


def timed_internal() -> "ContextManager[float]":
    """Context manager to time an internal query and record it."""
    return _TimedContext(is_internal=True)


def timed_external() -> "ContextManager[float]":
    """Context manager to time an external API call and record it."""
    return _TimedContext(is_internal=False)


class _TimedContext:
    """Context manager that measures elapsed time and records to metrics."""

    def __init__(self, *, is_internal: bool) -> None:
        self._is_internal = is_internal
        self._start: float = 0.0
        self._elapsed_ms: float = 0.0

    def __enter__(self) -> "_TimedContext":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        elapsed = (time.perf_counter() - self._start) * 1000
        self._elapsed_ms = elapsed
        if self._is_internal:
            record_internal(elapsed)
        else:
            record_external(elapsed)

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed_ms


# Optional: aggregate metrics across requests (for /api/metrics endpoint)
@dataclass
class AggregateMetrics:
    """Aggregate metrics across all requests (for /api/metrics endpoint)."""

    internal_count: int = 0
    external_count: int = 0
    internal_total_ms: float = 0.0
    external_total_ms: float = 0.0

    def record(self, internal_ms: float, external_ms: float) -> None:
        if internal_ms > 0:
            self.internal_count += 1
            self.internal_total_ms += internal_ms
        if external_ms > 0:
            self.external_count += 1
            self.external_total_ms += external_ms
        if internal_ms > 0 or external_ms > 0:
            logger.debug(
                "Request metrics: internal=%.2fms external=%.2fms",
                internal_ms,
                external_ms,
            )

    def to_dict(self) -> dict:
        return {
            "internal": {
                "count": self.internal_count,
                "total_ms": round(self.internal_total_ms, 2),
                "avg_ms": round(self.internal_total_ms / self.internal_count, 2)
                if self.internal_count > 0
                else 0,
            },
            "external": {
                "count": self.external_count,
                "total_ms": round(self.external_total_ms, 2),
                "avg_ms": round(self.external_total_ms / self.external_count, 2)
                if self.external_count > 0
                else 0,
            },
        }


aggregate_metrics = AggregateMetrics()
