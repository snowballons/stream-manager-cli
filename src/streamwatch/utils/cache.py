"""
Stream status caching module for StreamWatch application.

This module provides caching functionality to improve performance by reducing
redundant streamlink calls for recently checked streams.
"""

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional

from .. import config
from ..core.models import StreamStatus

logger = logging.getLogger(config.APP_NAME + ".cache")


@dataclass
class CacheEntry:
    """Represents a single cache entry with TTL support."""

    status: StreamStatus
    timestamp: float
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() - self.timestamp > self.ttl_seconds

    def time_until_expiry(self) -> float:
        """Get seconds until this entry expires (negative if already expired)."""
        return (self.timestamp + self.ttl_seconds) - time.time()


class StreamStatusCache:
    """
    Thread-safe cache for stream status information with TTL support.

    This cache stores stream liveness status to avoid redundant streamlink calls
    within a configurable time window.
    """

    def __init__(self, default_ttl_seconds: int = 300):
        """
        Initialize the cache.

        Args:
            default_ttl_seconds: Default TTL for cache entries in seconds (default: 5 minutes)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._default_ttl = default_ttl_seconds
        logger.debug(
            f"Initialized StreamStatusCache with default TTL: {default_ttl_seconds}s"
        )

    def get(self, url: str) -> Optional[StreamStatus]:
        """
        Get cached stream status for a URL.

        Args:
            url: The stream URL to look up

        Returns:
            StreamStatus if cached and not expired, None otherwise
        """
        with self._lock:
            entry = self._cache.get(url)
            if entry is None:
                logger.debug(f"Cache miss for URL: {url}")
                return None

            if entry.is_expired():
                logger.debug(f"Cache entry expired for URL: {url}")
                del self._cache[url]
                return None

            logger.debug(f"Cache hit for URL: {url}, status: {entry.status.value}")
            return entry.status

    def put(
        self, url: str, status: StreamStatus, ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Store stream status in cache.

        Args:
            url: The stream URL
            status: The stream status to cache
            ttl_seconds: TTL for this entry (uses default if None)
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl

        with self._lock:
            entry = CacheEntry(status=status, timestamp=time.time(), ttl_seconds=ttl)
            self._cache[url] = entry
            logger.debug(
                f"Cached status for URL: {url}, status: {status.value}, TTL: {ttl}s"
            )

    def invalidate(self, url: str) -> bool:
        """
        Remove a specific URL from cache.

        Args:
            url: The stream URL to invalidate

        Returns:
            True if entry was removed, False if not found
        """
        with self._lock:
            if url in self._cache:
                del self._cache[url]
                logger.debug(f"Invalidated cache entry for URL: {url}")
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries where URL contains the pattern.

        Args:
            pattern: String pattern to match in URLs

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            urls_to_remove = [url for url in self._cache.keys() if pattern in url]
            for url in urls_to_remove:
                del self._cache[url]

            if urls_to_remove:
                logger.debug(
                    f"Invalidated {len(urls_to_remove)} cache entries matching pattern: {pattern}"
                )

            return len(urls_to_remove)

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cache entries")
            return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of expired entries removed
        """
        with self._lock:
            expired_urls = [
                url for url, entry in self._cache.items() if entry.is_expired()
            ]

            for url in expired_urls:
                del self._cache[url]

            if expired_urls:
                logger.debug(f"Cleaned up {len(expired_urls)} expired cache entries")

            return len(expired_urls)

    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(
                1 for entry in self._cache.values() if entry.is_expired()
            )
            active_entries = total_entries - expired_entries

            return {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "expired_entries": expired_entries,
            }

    def get_cache_info(self) -> Dict[str, any]:
        """
        Get detailed cache information for debugging.

        Returns:
            Dictionary with detailed cache information
        """
        with self._lock:
            entries_info = []
            for url, entry in self._cache.items():
                entries_info.append(
                    {
                        "url": url,
                        "status": entry.status.value,
                        "age_seconds": time.time() - entry.timestamp,
                        "ttl_seconds": entry.ttl_seconds,
                        "time_until_expiry": entry.time_until_expiry(),
                        "is_expired": entry.is_expired(),
                    }
                )

            return {
                "default_ttl": self._default_ttl,
                "entries": entries_info,
                "stats": self.get_stats(),
            }


# Global cache instance
_global_cache: Optional[StreamStatusCache] = None
_cache_lock = Lock()


def get_cache() -> StreamStatusCache:
    """
    Get the global cache instance, creating it if necessary.

    Returns:
        The global StreamStatusCache instance
    """
    global _global_cache

    with _cache_lock:
        if _global_cache is None:
            # Get TTL from config, with fallback to 5 minutes
            ttl = (
                config.get_cache_ttl_seconds()
                if hasattr(config, "get_cache_ttl_seconds")
                else 300
            )
            _global_cache = StreamStatusCache(default_ttl_seconds=ttl)
            logger.info(f"Created global cache instance with TTL: {ttl}s")

        return _global_cache


def reset_cache() -> None:
    """Reset the global cache instance (mainly for testing)."""
    global _global_cache

    with _cache_lock:
        if _global_cache:
            _global_cache.clear()
        _global_cache = None
        logger.info("Reset global cache instance")
