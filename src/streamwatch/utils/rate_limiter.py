"""
Rate limiting module for StreamWatch application.

This module provides rate limiting functionality using the token bucket algorithm
to prevent overwhelming streaming platforms with too many requests.
"""

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional

from .. import config
from ..stream.utils import parse_url_metadata

logger = logging.getLogger(config.APP_NAME + ".rate_limiter")


@dataclass
class RateLimit:
    """Configuration for a rate limit."""

    requests_per_second: float
    burst_capacity: int

    def __post_init__(self) -> None:
        """Validate rate limit configuration."""
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.burst_capacity <= 0:
            raise ValueError("burst_capacity must be positive")


class TokenBucket:
    """
    Thread-safe token bucket implementation for rate limiting.

    The token bucket algorithm allows for burst traffic up to the bucket capacity,
    then enforces a steady rate of token replenishment.
    """

    def __init__(self, rate_limit: RateLimit):
        """
        Initialize the token bucket.

        Args:
            rate_limit: Rate limit configuration
        """
        self.rate_limit = rate_limit
        self.tokens = float(rate_limit.burst_capacity)  # Start with full bucket
        self.last_refill = time.time()
        self.lock = Lock()

        logger.debug(
            f"Created token bucket: {rate_limit.requests_per_second} req/s, "
            f"burst: {rate_limit.burst_capacity}"
        )

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time (called with lock held)."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.rate_limit.requests_per_second
        self.tokens = min(self.rate_limit.burst_capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        with self.lock:
            self._refill_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(f"Acquired {tokens} token(s), {self.tokens:.2f} remaining")
                return True

            logger.debug(
                f"Failed to acquire {tokens} token(s), {self.tokens:.2f} available"
            )
            return False

    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens, blocking if necessary.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait in seconds (None for no timeout)

        Returns:
            True if tokens were acquired, False if timeout occurred
        """
        start_time = time.time()

        while True:
            if self.try_acquire(tokens):
                return True

            # Check timeout
            if timeout is not None and (time.time() - start_time) >= timeout:
                logger.debug(f"Timeout acquiring {tokens} token(s)")
                return False

            # Calculate wait time until next token is available
            with self.lock:
                self._refill_tokens()
                if self.tokens >= tokens:
                    continue  # Try again immediately

                # Calculate how long to wait for enough tokens
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate_limit.requests_per_second
                wait_time = min(wait_time, 1.0)  # Cap at 1 second per iteration

            logger.debug(f"Waiting {wait_time:.2f}s for {tokens} token(s)")
            time.sleep(wait_time)

    def get_status(self) -> Dict[str, float]:
        """
        Get current bucket status.

        Returns:
            Dictionary with bucket status information
        """
        with self.lock:
            self._refill_tokens()
            return {
                "available_tokens": self.tokens,
                "capacity": float(self.rate_limit.burst_capacity),
                "rate_per_second": self.rate_limit.requests_per_second,
                "utilization": 1.0 - (self.tokens / self.rate_limit.burst_capacity),
            }


class RateLimiter:
    """
    Multi-platform rate limiter with global and per-platform limits.
    """

    def __init__(self) -> None:
        """Initialize the rate limiter with configured limits."""
        self.platform_buckets: Dict[str, TokenBucket] = {}
        self.global_bucket: Optional[TokenBucket] = None
        self.lock = Lock()

        self._initialize_buckets()
        logger.info("Rate limiter initialized")

    def _initialize_buckets(self) -> None:
        """Initialize token buckets from configuration."""
        # Global rate limit
        if config.get_rate_limit_enabled():
            global_limit = RateLimit(
                requests_per_second=config.get_rate_limit_global_requests_per_second(),
                burst_capacity=config.get_rate_limit_global_burst_capacity(),
            )
            self.global_bucket = TokenBucket(global_limit)
            logger.info(
                f"Global rate limit: {global_limit.requests_per_second} req/s, "
                f"burst: {global_limit.burst_capacity}"
            )

        # Platform-specific rate limits
        platform_configs = config.get_rate_limit_platform_configs()
        for platform, limit_config in platform_configs.items():
            rate_limit = RateLimit(
                requests_per_second=limit_config["requests_per_second"],
                burst_capacity=limit_config["burst_capacity"],
            )
            self.platform_buckets[platform] = TokenBucket(rate_limit)
            logger.info(
                f"{platform} rate limit: {rate_limit.requests_per_second} req/s, "
                f"burst: {rate_limit.burst_capacity}"
            )

    def _extract_platform(self, url: str) -> str:
        """
        Extract platform name from URL.

        Args:
            url: Stream URL

        Returns:
            Platform name (normalized)
        """
        try:
            metadata = parse_url_metadata(url)
            platform = metadata.get("platform", "Unknown").lower()

            # Normalize platform names to match configuration
            platform_mapping = {
                "twitch": "twitch",
                "youtube": "youtube",
                "kick": "kick",
                "bbc iplayer": "bbc",
                "zdf mediathek": "zdf",
            }

            return platform_mapping.get(platform, "default")
        except Exception as e:
            logger.warning(f"Failed to extract platform from {url}: {e}")
            return "default"

    def acquire(self, url: str, timeout: Optional[float] = None) -> bool:
        """
        Acquire rate limit permission for a URL.

        Args:
            url: Stream URL to check
            timeout: Maximum time to wait in seconds

        Returns:
            True if permission granted, False if timeout or rate limiting disabled
        """
        if not config.get_rate_limit_enabled():
            return True

        platform = self._extract_platform(url)
        logger.debug(f"Acquiring rate limit for {platform}: {url}")

        # Try global rate limit first
        if self.global_bucket:
            if not self.global_bucket.acquire(timeout=timeout):
                logger.info(f"Global rate limit exceeded for {url}")
                return False

        # Try platform-specific rate limit
        platform_bucket = self.platform_buckets.get(platform)
        if not platform_bucket:
            # Use default platform bucket if specific one not found
            platform_bucket = self.platform_buckets.get("default")

        if platform_bucket:
            if not platform_bucket.acquire(timeout=timeout):
                logger.info(f"{platform} rate limit exceeded for {url}")
                return False

        logger.debug(f"Rate limit acquired for {platform}: {url}")
        return True

    def try_acquire(self, url: str) -> bool:
        """
        Try to acquire rate limit permission without blocking.

        Args:
            url: Stream URL to check

        Returns:
            True if permission granted immediately, False otherwise
        """
        if not config.get_rate_limit_enabled():
            return True

        platform = self._extract_platform(url)

        # Check global rate limit first
        if self.global_bucket and not self.global_bucket.try_acquire():
            return False

        # Check platform-specific rate limit
        platform_bucket = self.platform_buckets.get(platform)
        if not platform_bucket:
            platform_bucket = self.platform_buckets.get("default")

        if platform_bucket and not platform_bucket.try_acquire():
            return False

        return True

    def get_status(self) -> Dict[str, Dict[str, float]]:
        """
        Get status of all rate limiters.

        Returns:
            Dictionary with status of global and platform rate limiters
        """
        status = {}

        if self.global_bucket:
            status["global"] = self.global_bucket.get_status()

        for platform, bucket in self.platform_buckets.items():
            status[platform] = bucket.get_status()

        return status


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = Lock()


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance, creating it if necessary.

    Returns:
        The global RateLimiter instance
    """
    global _global_rate_limiter

    with _rate_limiter_lock:
        if _global_rate_limiter is None:
            _global_rate_limiter = RateLimiter()

        return _global_rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter instance (mainly for testing)."""
    global _global_rate_limiter

    with _rate_limiter_lock:
        _global_rate_limiter = None
        logger.info("Reset global rate limiter instance")
