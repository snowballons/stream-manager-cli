"""
Performance monitoring utilities for StreamWatch.

Provides decorators and context managers for measuring and logging
performance metrics throughout the application.
"""

import functools
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar

from .logging_config import PerformanceLogger

F = TypeVar("F", bound=Callable[..., Any])


class PerformanceMonitor:
    """Central performance monitoring system."""

    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.logger = PerformanceLogger("monitor")

    def record_metric(self, name: str, value: float, unit: str = "ms", **tags) -> None:
        """Record a performance metric."""
        if name not in self.metrics:
            self.metrics[name] = {
                "count": 0,
                "total": 0.0,
                "min": float("inf"),
                "max": 0.0,
                "unit": unit,
            }

        metric = self.metrics[name]
        metric["count"] += 1
        metric["total"] += value
        metric["min"] = min(metric["min"], value)
        metric["max"] = max(metric["max"], value)

        # Log if significant
        if value > 1000:  # > 1 second
            self.logger.log_duration(name, value / 1000, **tags)

    def get_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a metric."""
        if name not in self.metrics:
            return None

        metric = self.metrics[name]
        if metric["count"] == 0:
            return metric

        return {**metric, "avg": metric["total"] / metric["count"]}

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get all performance statistics."""
        return {name: self.get_stats(name) for name in self.metrics}


# Global performance monitor instance
_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    return _monitor


@contextmanager
def measure_time(operation_name: str, **tags):
    """Context manager to measure execution time."""
    start_time = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _monitor.record_metric(operation_name, duration_ms, "ms", **tags)


def timed(operation_name: Optional[str] = None, **default_tags):
    """Decorator to measure function execution time."""

    def decorator(func: F) -> F:
        name = operation_name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tags = {**default_tags}

            # Add function-specific tags
            if hasattr(func, "__self__"):
                tags["class"] = func.__self__.__class__.__name__

            with measure_time(name, **tags):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def count_calls(operation_name: Optional[str] = None):
    """Decorator to count function calls."""

    def decorator(func: F) -> F:
        name = operation_name or f"{func.__module__}.{func.__name__}_calls"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _monitor.record_metric(name, 1, "count")
            return func(*args, **kwargs)

        return wrapper

    return decorator


class StreamPerformanceTracker:
    """Specialized performance tracker for stream operations."""

    def __init__(self):
        self.logger = PerformanceLogger("streams")

    def track_stream_check(self, url: str, duration_ms: float, success: bool) -> None:
        """Track stream liveness check performance."""
        _monitor.record_metric(
            "stream_check_duration",
            duration_ms,
            "ms",
            success=success,
            platform=self._extract_platform(url),
        )

        if duration_ms > 5000:  # > 5 seconds
            self.logger.log_duration(
                "slow_stream_check", duration_ms / 1000, url=url[:50], success=success
            )

    def track_metadata_fetch(self, url: str, duration_ms: float, success: bool) -> None:
        """Track metadata fetch performance."""
        _monitor.record_metric(
            "metadata_fetch_duration",
            duration_ms,
            "ms",
            success=success,
            platform=self._extract_platform(url),
        )

    def track_batch_operation(
        self, operation: str, count: int, duration_ms: float
    ) -> None:
        """Track batch operation performance."""
        _monitor.record_metric(f"batch_{operation}_duration", duration_ms, "ms")
        _monitor.record_metric(f"batch_{operation}_count", count, "count")

        # Calculate throughput
        if duration_ms > 0:
            throughput = (count * 1000) / duration_ms  # items per second
            _monitor.record_metric(
                f"batch_{operation}_throughput", throughput, "items/sec"
            )

    def _extract_platform(self, url: str) -> str:
        """Extract platform from URL for tagging."""
        if "twitch.tv" in url:
            return "twitch"
        elif "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        elif "kick.com" in url:
            return "kick"
        else:
            return "unknown"


# Global stream performance tracker
_stream_tracker = StreamPerformanceTracker()


def get_stream_performance_tracker() -> StreamPerformanceTracker:
    """Get the global stream performance tracker."""
    return _stream_tracker


# Memory usage tracking
def get_memory_usage() -> Dict[str, float]:
    """Get current memory usage statistics."""
    try:
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
            "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            "percent": process.memory_percent(),
        }
    except ImportError:
        # Fallback if psutil not available
        import tracemalloc

        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            return {"current_mb": current / 1024 / 1024, "peak_mb": peak / 1024 / 1024}
        return {}


@contextmanager
def memory_profiling(operation_name: str):
    """Context manager for memory profiling."""
    import tracemalloc

    if not tracemalloc.is_tracing():
        tracemalloc.start()

    snapshot_before = tracemalloc.take_snapshot()

    try:
        yield
    finally:
        snapshot_after = tracemalloc.take_snapshot()

        # Calculate memory difference
        top_stats = snapshot_after.compare_to(snapshot_before, "lineno")

        total_diff = sum(stat.size_diff for stat in top_stats)
        if total_diff > 1024 * 1024:  # > 1MB difference
            logger = PerformanceLogger("memory")
            logger.logger.warning(
                f"Memory usage increased by {total_diff / 1024 / 1024:.2f}MB during {operation_name}"
            )
