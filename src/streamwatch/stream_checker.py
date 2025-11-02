import asyncio  # For async/await support
import json  # For parsing --json output
import logging  # Import logging
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union

from . import config
from .cache import get_cache
from .exceptions import (
    AuthenticationError,
    NetworkError,
    RateLimitExceededError,
    StreamlinkError,
    StreamNotFoundError,
    TimeoutError,
    categorize_streamlink_error,
)
from .models import StreamInfo, StreamMetadata, StreamStatus
from .performance import get_stream_performance_tracker, measure_time, timed
from .rate_limiter import get_rate_limiter
from .resilience import (
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    RetryConfig,
    get_circuit_breaker,
    resilient_operation,
)
from .result import Result, StreamResult, safe_call
from .stream_utils import parse_url_metadata

# Get a logger for this module
logger = logging.getLogger(config.APP_NAME + ".stream_checker")


class StreamCheckResult:
    """
    Represents the result of a stream liveness check with detailed error information.
    """

    def __init__(
        self, is_live: bool, url: str, error: Optional[StreamlinkError] = None
    ):
        """
        Initialize StreamCheckResult.

        Args:
            is_live: Whether the stream is live
            url: The stream URL that was checked
            error: Detailed error information if check failed
        """
        self.is_live = is_live
        self.url = url
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for structured logging/debugging."""
        result = {"is_live": self.is_live, "url": self.url}
        if self.error:
            result["error"] = self.error.to_dict()
        return result


class MetadataResult:
    """
    Represents the result of a stream metadata fetch with detailed error information.
    """

    def __init__(
        self,
        success: bool,
        url: str,
        json_data: Optional[str] = None,
        error: Optional[StreamlinkError] = None,
    ):
        """
        Initialize MetadataResult.

        Args:
            success: Whether the metadata fetch was successful
            url: The stream URL that was processed
            json_data: The JSON metadata string if successful
            error: Detailed error information if fetch failed
        """
        self.success = success
        self.url = url
        self.json_data = json_data
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for structured logging/debugging."""
        result = {
            "success": self.success,
            "url": self.url,
            "has_json_data": self.json_data is not None,
        }
        if self.error:
            result["error"] = self.error.to_dict()
        return result


# --- Dependency Injection Interfaces ---


class CacheInterface(Protocol):
    """Interface for cache implementations."""

    def get(self, key: str) -> Optional[StreamStatus]:
        ...

    def put(self, key: str, value: StreamStatus) -> None:
        ...


class RateLimiterInterface(Protocol):
    """Interface for rate limiter implementations."""

    def acquire(self, key: str, timeout: float = None) -> bool:
        ...


class ConfigInterface(Protocol):
    """Interface for configuration access."""

    def get_cache_enabled(self) -> bool:
        ...

    def get_rate_limit_enabled(self) -> bool:
        ...

    def get_streamlink_timeout_liveness(self) -> int:
        ...

    def get_streamlink_timeout_metadata(self) -> int:
        ...

    def get_max_workers_liveness(self) -> int:
        ...

    def get_max_workers_metadata(self) -> int:
        ...


# --- StreamChecker Class with Dependency Injection ---


class StreamChecker:
    """
    Stream checking service with dependency injection for better testability.
    """

    def __init__(
        self,
        cache: Optional[CacheInterface] = None,
        rate_limiter: Optional[RateLimiterInterface] = None,
        config_provider: Optional[ConfigInterface] = None,
    ):
        """
        Initialize StreamChecker with dependencies.

        Args:
            cache: Cache implementation (optional)
            rate_limiter: Rate limiter implementation (optional)
            config_provider: Configuration provider (optional)
        """
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.config = config_provider or config
        self.logger = logging.getLogger(config.APP_NAME + ".stream_checker")

    def check_stream_liveness(self, url: str) -> StreamResult:
        """
        Check stream liveness with dependency injection.

        Args:
            url: Stream URL to check

        Returns:
            Result containing StreamCheckResult or error message
        """
        if not url or not isinstance(url, str):
            return Result.Err("Invalid URL provided")

        # Check cache if available
        if self.cache and self.config.get_cache_enabled():
            cached_status = self.cache.get(url)
            if cached_status is not None:
                self.logger.debug(
                    f"Using cached status for {url}: {cached_status.value}"
                )
                result = StreamCheckResult(
                    is_live=(cached_status == StreamStatus.LIVE), url=url
                )
                return Result.Ok(result)

        # Apply rate limiting if available
        if self.rate_limiter and self.config.get_rate_limit_enabled():
            timeout = self.config.get_streamlink_timeout_liveness()
            if not self.rate_limiter.acquire(url, timeout=timeout):
                return Result.Err(f"Rate limit exceeded for {url}")

        # Perform the actual check
        check_result = safe_call(self._check_stream_core, url)

        if check_result.is_err():
            return Result.Err(f"Stream check failed: {check_result.unwrap_err()}")

        result = check_result.unwrap()

        # Update cache if available
        if self.cache and self.config.get_cache_enabled():
            status = StreamStatus.LIVE if result.is_live else StreamStatus.OFFLINE
            if result.error and isinstance(result.error, StreamNotFoundError):
                status = StreamStatus.OFFLINE
            elif result.error:
                status = StreamStatus.ERROR

            self.cache.put(url, status)
            self.logger.debug(f"Cached status for {url}: {status.value}")

        return Result.Ok(result)

    def fetch_metadata(self, url: str) -> StreamResult:
        """
        Fetch stream metadata with dependency injection.

        Args:
            url: Stream URL to fetch metadata for

        Returns:
            Result containing MetadataResult or error message
        """
        if not url or not isinstance(url, str):
            return Result.Err("Invalid URL provided")

        # Apply rate limiting if available
        if self.rate_limiter and self.config.get_rate_limit_enabled():
            timeout = self.config.get_streamlink_timeout_metadata()
            if not self.rate_limiter.acquire(url, timeout=timeout):
                return Result.Err(f"Rate limit exceeded for {url}")

        # Perform the metadata fetch
        metadata_result = safe_call(self._fetch_metadata_core, url)

        if metadata_result.is_err():
            return Result.Err(f"Metadata fetch failed: {metadata_result.unwrap_err()}")

        return Result.Ok(metadata_result.unwrap())

    def _check_stream_core(self, url: str) -> StreamCheckResult:
        """Core stream checking logic without dependencies."""
        command = ["streamlink"]
        if (
            hasattr(self.config, "get_twitch_disable_ads")
            and self.config.get_twitch_disable_ads()
        ):
            command.append("--twitch-disable-ads")
        command.append(url)

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.config.get_streamlink_timeout_liveness(),
                check=False,
            )

            if process.returncode == 0 and "Available streams:" in process.stdout:
                self.logger.debug(f"Stream is live: {url}")
                return StreamCheckResult(is_live=True, url=url)

            # Stream is not live or error occurred
            error = categorize_streamlink_error(
                stderr=process.stderr or "",
                stdout=process.stdout or "",
                return_code=process.returncode,
                url=url,
            )

            if isinstance(error, StreamNotFoundError):
                self.logger.info(f"Stream is not live: {url} - {error}")
            else:
                self.logger.warning(f"Stream check failed: {url} - {error}")

            return StreamCheckResult(is_live=False, url=url, error=error)

        except subprocess.TimeoutExpired:
            error = TimeoutError(
                f"Timeout expired checking liveness for: {url}", url=url
            )
            self.logger.warning(f"Timeout expired checking liveness for: {url}")
            return StreamCheckResult(is_live=False, url=url, error=error)

        except Exception as e:
            error = StreamlinkError(
                f"Unexpected error checking liveness: {str(e)}", url=url
            )
            self.logger.exception(f"Error checking liveness for {url}")
            return StreamCheckResult(is_live=False, url=url, error=error)

    def _fetch_metadata_core(self, url: str) -> "MetadataResult":
        """Core metadata fetching logic without dependencies."""
        command = ["streamlink", "--json", url]

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.config.get_streamlink_timeout_metadata(),
                check=False,
            )

            if process.returncode == 0 and process.stdout.strip():
                return MetadataResult(
                    success=True, url=url, json_data=process.stdout.strip()
                )

            error = categorize_streamlink_error(
                stderr=process.stderr or "",
                stdout=process.stdout or "",
                return_code=process.returncode,
                url=url,
            )

            return MetadataResult(success=False, url=url, error=error)

        except subprocess.TimeoutExpired:
            error = TimeoutError(
                f"Timeout expired fetching metadata for: {url}", url=url
            )
            return MetadataResult(success=False, url=url, error=error)

        except Exception as e:
            error = StreamlinkError(
                f"Unexpected error fetching metadata: {str(e)}", url=url
            )
            return MetadataResult(success=False, url=url, error=error)


# --- Factory Function for Backward Compatibility ---


def create_stream_checker() -> StreamChecker:
    """Create StreamChecker with default dependencies."""
    try:
        from .cache import get_cache

        cache = get_cache()
    except ImportError:
        cache = None

    try:
        from .rate_limiter import get_rate_limiter

        rate_limiter = get_rate_limiter()
    except ImportError:
        rate_limiter = None

    return StreamChecker(cache=cache, rate_limiter=rate_limiter)


# Get a logger for this module
logger = logging.getLogger(config.APP_NAME + ".stream_checker")


def sanitize_category_string(category: str) -> str:
    """
    Sanitize category string to ensure it passes Pydantic validation.

    The category validation only allows:
    letters, numbers, spaces, hyphens, underscores, dots, parentheses, brackets, ampersands, forward slashes

    Args:
        category: Raw category string from metadata

    Returns:
        Sanitized category string that passes validation
    """
    if not category or category == "N/A":
        return "N/A"

    # Convert to string and strip
    category = str(category).strip()

    # Remove or replace invalid characters
    # Keep only allowed characters: [a-zA-Z0-9\s\-_\.\(\)\[\]\&/]
    import re

    # Replace common problematic characters with safe alternatives
    replacements = {
        ":": " -",  # colon to dash
        ";": ",",  # semicolon to comma
        '"': "",  # remove quotes
        "'": "",  # remove apostrophes
        "`": "",  # remove backticks
        "*": "",  # remove asterisks
        "+": "",  # remove plus signs
        "=": "",  # remove equals
        "|": " ",  # pipe to space
        "\\": " ",  # backslash to space
        "~": "",  # remove tilde
        "#": "",  # remove hash
        "%": "",  # remove percent
        "^": "",  # remove caret
        "?": "",  # remove question mark
        "!": "",  # remove exclamation
        "<": "(",  # less-than to parenthesis
        ">": ")",  # greater-than to parenthesis
        "{": "(",  # curly brace to parenthesis
        "}": ")",  # curly brace to parenthesis
        "@": "",  # remove at symbol
        "$": "",  # remove dollar sign
    }

    for old_char, new_char in replacements.items():
        category = category.replace(old_char, new_char)

    # Keep only allowed characters using regex
    # Allowed: letters, numbers, spaces, hyphens, underscores, dots, parentheses, brackets, ampersands, forward slashes
    category = re.sub(r"[^a-zA-Z0-9\s\-_\.\(\)\[\]\&/]", "", category)

    # Clean up multiple spaces and trim
    category = re.sub(r"\s+", " ", category).strip()

    # Limit length to prevent validation errors
    if len(category) > 100:  # MAX_CATEGORY_LENGTH from validators
        category = category[:97] + "..."

    # Return N/A if empty after sanitization
    return category if category else "N/A"


def _get_retry_config() -> RetryConfig:
    """Get retry configuration from app config."""
    return RetryConfig(
        max_attempts=config.get_retry_max_attempts(),
        base_delay=config.get_retry_base_delay(),
        max_delay=config.get_retry_max_delay(),
        exponential_base=config.get_retry_exponential_base(),
        jitter=config.get_retry_jitter(),
    )


def _get_circuit_breaker_config() -> CircuitBreakerConfig:
    """Get circuit breaker configuration from app config."""
    return CircuitBreakerConfig(
        failure_threshold=config.get_circuit_breaker_failure_threshold(),
        recovery_timeout=config.get_circuit_breaker_recovery_timeout(),
        success_threshold=config.get_circuit_breaker_success_threshold(),
    )


class StreamCheckResult:
    """
    Represents the result of a stream liveness check with detailed error information.
    """

    def __init__(
        self, is_live: bool, url: str, error: Optional[StreamlinkError] = None
    ):
        """
        Initialize StreamCheckResult.

        Args:
            is_live: Whether the stream is live
            url: The stream URL that was checked
            error: Detailed error information if check failed
        """
        self.is_live = is_live
        self.url = url
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for structured logging/debugging."""
        result = {"is_live": self.is_live, "url": self.url}
        if self.error:
            result["error"] = self.error.to_dict()
        return result


class MetadataResult:
    """
    Represents the result of a stream metadata fetch with detailed error information.
    """

    def __init__(
        self,
        success: bool,
        url: str,
        json_data: Optional[str] = None,
        error: Optional[StreamlinkError] = None,
    ):
        """
        Initialize MetadataResult.

        Args:
            success: Whether the metadata fetch was successful
            url: The stream URL that was processed
            json_data: The JSON metadata string if successful
            error: Detailed error information if fetch failed
        """
        self.success = success
        self.url = url
        self.json_data = json_data
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for structured logging/debugging."""
        result = {
            "success": self.success,
            "url": self.url,
            "has_json_data": self.json_data is not None,
        }
        if self.error:
            result["error"] = self.error.to_dict()
        return result


def is_stream_live_for_check(url: str) -> Tuple[bool, str]:
    """
    Checks if a given stream URL is currently live using streamlink.

    This is a backward-compatible wrapper around is_stream_live_for_check_detailed
    for existing code that expects the old return format.

    Args:
        url: The stream URL to check

    Returns:
        Tuple of (is_live, url)
    """
    result = is_stream_live_for_check_detailed(url)
    return result.is_live, result.url


def _is_stream_live_core(url: str) -> StreamCheckResult:
    """
    Core implementation for checking if a stream URL is live.
    This is the base function without resilience patterns.

    Args:
        url: The stream URL to check

    Returns:
        StreamCheckResult: Detailed result with error categorization
    """
    command = ["streamlink"]
    if config.get_twitch_disable_ads():
        command.append("--twitch-disable-ads")
    command.append(url)

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=config.get_streamlink_timeout_liveness(),
            check=False,
        )

        if process.returncode == 0 and "Available streams:" in process.stdout:
            logger.debug(f"Stream is live: {url}")
            return StreamCheckResult(is_live=True, url=url)

        # Stream is not live or error occurred - categorize the error
        error = categorize_streamlink_error(
            stderr=process.stderr or "",
            stdout=process.stdout or "",
            return_code=process.returncode,
            url=url,
        )

        # Log appropriate level based on error type
        if isinstance(error, StreamNotFoundError):
            logger.info(f"Stream is not live: {url} - {error}")
        elif isinstance(error, (NetworkError, AuthenticationError)):
            logger.warning(f"Stream check failed: {url} - {error}")
        else:
            logger.warning(f"Ambiguous liveness result for: {url} - {error}")

        return StreamCheckResult(is_live=False, url=url, error=error)

    except subprocess.TimeoutExpired:
        error = TimeoutError(f"Timeout expired checking liveness for: {url}", url=url)
        logger.warning(f"Timeout expired checking liveness for: {url}")
        return StreamCheckResult(is_live=False, url=url, error=error)

    except FileNotFoundError:
        logger.critical("streamlink command not found during check.")
        raise FileNotFoundError("streamlink command not found during check.")

    except Exception as e:
        # Wrap unexpected exceptions in StreamlinkError
        error = StreamlinkError(
            f"Unexpected error checking liveness: {str(e)}", url=url
        )
        logger.exception(f"Error checking liveness for {url}")
        return StreamCheckResult(is_live=False, url=url, error=error)


def is_stream_live_for_check_detailed(url: str) -> StreamCheckResult:
    """
    Checks if a given stream URL is currently live using streamlink with detailed error information,
    resilience patterns (retry logic and circuit breaker), caching, and rate limiting.

    Args:
        url: The stream URL to check

    Returns:
        StreamCheckResult: Detailed result with error categorization
    """
    # Check cache first if caching is enabled
    if config.get_cache_enabled():
        cache = get_cache()
        cached_status = cache.get(url)
        if cached_status is not None:
            logger.debug(f"Using cached status for {url}: {cached_status.value}")
            # Convert cached status to StreamCheckResult
            is_live = cached_status == StreamStatus.LIVE
            return StreamCheckResult(is_live=is_live, url=url)

    # Apply rate limiting before making streamlink call
    if config.get_rate_limit_enabled():
        rate_limiter = get_rate_limiter()
        timeout = (
            config.get_streamlink_timeout_liveness()
        )  # Use streamlink timeout as rate limit timeout

        if not rate_limiter.acquire(url, timeout=timeout):
            # Rate limit exceeded
            from .stream_utils import parse_url_metadata

            platform = parse_url_metadata(url).get("platform", "Unknown")
            error = RateLimitExceededError(
                f"Rate limit exceeded for {platform}", url=url, platform=platform
            )
            logger.warning(f"Rate limit exceeded for {url}")
            return StreamCheckResult(is_live=False, url=url, error=error)

    # Cache miss or caching disabled - perform actual check
    if not config.get_circuit_breaker_enabled():
        # If resilience is disabled, use the core function directly
        result = _is_stream_live_core(url)
    else:
        try:
            # Use resilient operation with retry and circuit breaker
            @resilient_operation(
                operation_name=f"stream_liveness_check_{url}",
                retry_config=_get_retry_config(),
                circuit_breaker_config=_get_circuit_breaker_config(),
                use_circuit_breaker=True,
            )
            def resilient_check():
                result = _is_stream_live_core(url)
                # If the result indicates an error that should trigger circuit breaker,
                # raise the exception to be handled by resilience patterns
                if result.error and isinstance(
                    result.error, (NetworkError, TimeoutError)
                ):
                    raise result.error
                return result

            result = resilient_check()

        except CircuitBreakerOpenError as e:
            # Circuit breaker is open - return a specific error
            error = NetworkError(
                f"Circuit breaker open for stream checks: {str(e)}", url=url
            )
            logger.warning(f"Circuit breaker open for stream liveness check: {url}")
            result = StreamCheckResult(is_live=False, url=url, error=error)

        except Exception as e:
            # Handle any other exceptions from resilience patterns
            if isinstance(e, StreamlinkError):
                result = StreamCheckResult(is_live=False, url=url, error=e)
            else:
                error = StreamlinkError(f"Resilience pattern error: {str(e)}", url=url)
                result = StreamCheckResult(is_live=False, url=url, error=error)

    # Update cache with the result if caching is enabled
    if config.get_cache_enabled():
        cache = get_cache()
        # Determine status to cache based on result
        if result.is_live:
            status = StreamStatus.LIVE
        elif result.error and isinstance(result.error, StreamNotFoundError):
            status = StreamStatus.OFFLINE
        elif result.error:
            status = StreamStatus.ERROR
        else:
            status = StreamStatus.OFFLINE

        cache.put(url, status)
        logger.debug(f"Cached status for {url}: {status.value}")

    return result


def get_stream_metadata_json(url: str) -> Tuple[bool, str]:
    """
    Fetches stream metadata using streamlink --json.

    This is a backward-compatible wrapper around get_stream_metadata_json_detailed
    for existing code that expects the old return format.

    Args:
        url: The stream URL to get metadata for

    Returns:
        Tuple of (success, json_string_or_error_message)
    """
    try:
        result = get_stream_metadata_json_detailed(url)
        if result.success:
            return (True, result.json_data)
        else:
            return (False, str(result.error) if result.error else "Unknown error")
    except Exception as e:
        return (False, str(e))


def _build_metadata_command(url: str) -> List[str]:
    """
    Build streamlink command for metadata fetching.

    Args:
        url: Stream URL

    Returns:
        Command list for subprocess
    """
    command = ["streamlink", "--json", url]

    # Add Twitch-specific flags if needed
    if config.get_twitch_disable_ads() and "twitch.tv" in url:
        command.insert(1, "--twitch-disable-ads")

    return command


def _validate_json_response(stdout: str, url: str) -> MetadataResult:
    """
    Validate JSON response from streamlink.

    Args:
        stdout: Raw stdout from streamlink
        url: Stream URL for error context

    Returns:
        MetadataResult with validation outcome
    """
    if not stdout or not stdout.strip():
        error = StreamlinkError("Empty JSON response", url=url)
        return MetadataResult(success=False, url=url, error=error)

    try:
        # Validate JSON format
        json.loads(stdout)
        return MetadataResult(success=True, json_data=stdout.strip(), url=url)
    except json.JSONDecodeError as e:
        error = StreamlinkError(
            f"Invalid JSON response: {str(e)}", url=url, stdout=stdout
        )
        logger.warning(f"Could not process JSON for {url}: {e}")
        return MetadataResult(success=False, url=url, error=error)


def _handle_metadata_process_result(
    process: subprocess.CompletedProcess, url: str
) -> MetadataResult:
    """
    Handle the result of metadata subprocess execution.

    Args:
        process: Completed subprocess
        url: Stream URL for error context

    Returns:
        MetadataResult with processed outcome
    """
    if process.returncode == 0 and process.stdout:
        return _validate_json_response(process.stdout, url)

    # Metadata fetch failed - categorize the error
    error = categorize_streamlink_error(
        stderr=process.stderr or "",
        stdout=process.stdout or "",
        return_code=process.returncode,
        url=url,
    )

    logger.warning(f"streamlink --json for {url} failed - {error}")
    return MetadataResult(success=False, url=url, error=error)


def _get_stream_metadata_core(url: str) -> "MetadataResult":
    """
    Core implementation for fetching stream metadata.
    Refactored into smaller, focused functions.

    Args:
        url: The stream URL to get metadata for

    Returns:
        MetadataResult: Detailed result with error categorization
    """
    command = _build_metadata_command(url)

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=config.get_streamlink_timeout_metadata(),
            check=False,
        )

        return _handle_metadata_process_result(process, url)

    except subprocess.TimeoutExpired:
        error = TimeoutError(f"Timeout fetching JSON metadata for {url}", url=url)
        logger.warning(f"Timeout fetching JSON metadata for {url}")
        return MetadataResult(success=False, url=url, error=error)

    except FileNotFoundError:
        logger.critical("streamlink command not found during JSON metadata fetch.")
        raise FileNotFoundError(
            "streamlink command not found during JSON metadata fetch."
        )
    except Exception as e:
        error = StreamlinkError(
            f"Unexpected error fetching metadata: {str(e)}", url=url
        )
        logger.exception(f"Error fetching JSON metadata for {url}")
        return MetadataResult(success=False, url=url, error=error)


def get_stream_metadata_json_detailed(url: str) -> "MetadataResult":
    """
    Fetches stream metadata using streamlink --json with detailed error information,
    resilience patterns (retry logic and circuit breaker), and rate limiting.

    Args:
        url: The stream URL to get metadata for

    Returns:
        MetadataResult: Detailed result with error categorization
    """
    # Apply rate limiting before making streamlink call
    if config.get_rate_limit_enabled():
        rate_limiter = get_rate_limiter()
        timeout = (
            config.get_streamlink_timeout_metadata()
        )  # Use metadata timeout as rate limit timeout

        if not rate_limiter.acquire(url, timeout=timeout):
            # Rate limit exceeded
            from .stream_utils import parse_url_metadata

            platform = parse_url_metadata(url).get("platform", "Unknown")
            error = RateLimitExceededError(
                f"Rate limit exceeded for {platform} metadata fetch",
                url=url,
                platform=platform,
            )
            logger.warning(f"Rate limit exceeded for metadata fetch: {url}")
            return MetadataResult(success=False, url=url, error=error)

    if not config.get_circuit_breaker_enabled():
        # If resilience is disabled, use the core function directly
        return _get_stream_metadata_core(url)

    try:
        # Use resilient operation with retry and circuit breaker
        @resilient_operation(
            operation_name=f"stream_metadata_fetch_{url}",
            retry_config=_get_retry_config(),
            circuit_breaker_config=_get_circuit_breaker_config(),
            use_circuit_breaker=True,
        )
        def resilient_fetch():
            result = _get_stream_metadata_core(url)
            # If the result indicates an error that should trigger circuit breaker,
            # raise the exception to be handled by resilience patterns
            if (
                not result.success
                and result.error
                and isinstance(result.error, (NetworkError, TimeoutError))
            ):
                raise result.error
            return result

        return resilient_fetch()

    except CircuitBreakerOpenError as e:
        # Circuit breaker is open - return a specific error
        error = NetworkError(
            f"Circuit breaker open for metadata fetch: {str(e)}", url=url
        )
        logger.warning(f"Circuit breaker open for metadata fetch: {url}")
        return MetadataResult(success=False, url=url, error=error)

    except Exception as e:
        # Handle any other exceptions from resilience patterns
        if isinstance(e, StreamlinkError):
            return MetadataResult(success=False, url=url, error=e)
        else:
            error = StreamlinkError(f"Resilience pattern error: {str(e)}", url=url)
            return MetadataResult(success=False, url=url, error=error)


def extract_category_keywords(
    metadata_result: Tuple[bool, str], platform: str, url_type: str = "unknown"
) -> str:
    """Extracts category/keywords from streamlink's JSON metadata based on platform.

    Args:
        metadata_result: Tuple of (success, json_string_or_error) from get_stream_metadata_json
        platform: The platform name (e.g., 'Twitch', 'YouTube')
        url_type: The type of URL being processed

    Returns:
        Category string or 'N/A' if not found
    """
    success, json_data = metadata_result
    if not success:
        return "N/A"

    try:
        metadata_json = json.loads(json_data)
    except json.JSONDecodeError:
        return "N/A"

    if not metadata_json or "metadata" not in metadata_json:
        return "N/A"
    meta = metadata_json.get("metadata", {})
    title = meta.get("title", "")

    # Helper to clean titles
    def clean_common_prefixes(text: str) -> str:
        return re.sub(
            r"^\(?(LIVE|EN DIRECT|ОНЛАЙН|생방송|ライブ)[\]:]*\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

    # --- Platform Specific Logic ---
    if platform == "Twitch":
        return str(meta.get("game") or (title.split(" ")[0] if title else "N/A"))

    elif platform == "YouTube":
        clean_title = clean_common_prefixes(title)
        words = clean_title.split()
        if (
            len(words) > 0
            and len(words[0]) <= 2
            and len(words) > 1
            and words[0].upper()
            not in [
                "A",
                "AN",
                "BE",
                "IN",
                "IS",
                "IT",
                "OF",
                "ON",
                "OR",
                "SO",
                "TO",
                "EL",
                "LA",
                "DE",
            ]
        ):
            return " ".join(words[1:4]) if len(words) > 1 else clean_title
        return " ".join(words[:3]) if words else "N/A"

    elif platform == "Kick":
        # Kick often has category in title or a specific field if plugin supports
        # Assuming title is primary for now if no dedicated field found in your tests
        return (
            title.split(":")[0].strip()
            if ":" in title
            else (title.split(" ")[0] if title else "N/A")
        )

    elif platform == "TikTok" or platform == "Douyin" or platform == "Bigo Live":
        # Title is primary; may contain hints.
        return (
            clean_common_prefixes(title) if title else "N/A"
        )  # Return more of the title

    elif platform == "BiliBili":
        category = meta.get("game_name", meta.get("category"))
        if category:
            return str(category)
        return (
            clean_common_prefixes(title).split(" - ")[0]
            if " - " in title
            else (title.split(" ")[0] if title else "N/A")
        )

    elif platform == "Vimeo" or platform == "Dailymotion":
        # Title usually contains event/stream description
        return clean_common_prefixes(title) if title else "N/A"

    elif platform == "PlutoTV":
        return (
            meta.get("program_title") or meta.get("title") or "Live TV"
        )  # Current show

    elif platform == "Huya":
        return str(
            meta.get("game_name", meta.get("category"))
            or (title.split(" ")[0] if title else "N/A")
        )

    elif platform in [
        "BBC iPlayer",
        "RaiPlay",
        "Atresplayer",
        "RTVE Play",
        "ARD Mediathek",
        "ZDF Mediathek",
        "Mitele",
        "AbemaTV",
    ]:
        # For broadcasters, the program title is the category
        return meta.get("program_title", meta.get("title")) or "Live Broadcast"

    elif platform == "Adult Swim":
        return meta.get("title") or "Live Stream"  # Title is often the show

    elif platform == "Bloomberg":
        return meta.get("title") or "Live News"  # Title is the show/feed

    # --- Generic Fallback ---
    if title:
        clean_title = clean_common_prefixes(title)
        return " ".join(
            clean_title.split()[:3]
        )  # First 3 words of cleaned title as a generic category
    return "N/A"


@timed("fetch_live_streams")
def fetch_live_streams(
    all_configured_streams_data: List[Dict[str, str]],
    use_async: bool = True,
) -> List[Dict[str, Any]]:
    """
    Fetches the list of currently live streams with enhanced metadata.
    Optimized with async/await for concurrent processing or fallback to threading.

    Args:
        all_configured_streams_data: List of configured stream dictionaries
        use_async: Whether to use async concurrent processing (default: True)

    Returns:
        List of dictionaries with stream info including live status and metadata
    """
    if not all_configured_streams_data:
        logger.info("No configured streams to check.")
        return []

    logger.info(f"Checking {len(all_configured_streams_data)} streams for liveness...")

    if use_async and len(all_configured_streams_data) > 1:
        # Use async concurrent processing for better performance
        try:
            return asyncio.run(
                _fetch_live_streams_async_impl(all_configured_streams_data)
            )
        except Exception as e:
            logger.warning(f"Async processing failed, falling back to threading: {e}")
            # Fall through to threading implementation

    # Fallback to original threading implementation
    # Phase 1: Optimized batch liveness check
    with measure_time(
        "batch_liveness_check", stream_count=len(all_configured_streams_data)
    ):
        live_stream_candidates = _batch_check_liveness(all_configured_streams_data)

    if not live_stream_candidates:
        logger.info("No streams appear to be live based on initial check.")
        return []

    logger.info(f"Found {len(live_stream_candidates)} potentially live stream(s).")

    # Phase 2: Optimized batch metadata fetch
    with measure_time("batch_metadata_fetch", stream_count=len(live_stream_candidates)):
        live_streams_info = _batch_fetch_metadata(
            live_stream_candidates, all_configured_streams_data
        )

    # Track performance
    tracker = get_stream_performance_tracker()
    tracker.track_batch_operation(
        "stream_check", len(all_configured_streams_data), 0
    )  # Duration tracked by decorator

    # Return the list of enhanced objects, converted to dictionaries for compatibility
    return [s.model_dump() for s in live_streams_info]


async def _fetch_live_streams_async_impl(
    all_configured_streams_data: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    Internal async implementation for fetch_live_streams.

    Args:
        all_configured_streams_data: List of configured stream dictionaries

    Returns:
        List of live stream info dictionaries
    """
    from .async_stream_checker import create_async_stream_checker

    checker = create_async_stream_checker()
    return await checker.fetch_live_streams_async(all_configured_streams_data)


def _batch_check_liveness(
    all_configured_streams_data: List[Dict[str, str]]
) -> List[str]:
    """
    Optimized batch liveness checking with proper error handling.

    Args:
        all_configured_streams_data: List of configured stream dictionaries

    Returns:
        List of URLs that are live
    """
    all_configured_urls = [s["url"] for s in all_configured_streams_data]
    live_stream_candidates = []
    max_workers = min(config.get_max_workers_liveness(), len(all_configured_urls))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_url = {
            executor.submit(is_stream_live_for_check_detailed, url): url
            for url in all_configured_urls
        }

        # Process results as they complete
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result(
                    timeout=config.get_streamlink_timeout_liveness() + 5
                )
                if result.is_live:
                    live_stream_candidates.append(url)
                elif result.error:
                    logger.debug(f"Stream check failed for {url}: {result.error}")
            except Exception as e:
                logger.warning(f"Unexpected error checking {url}: {e}")

    return live_stream_candidates


def _batch_fetch_metadata(
    live_urls: List[str], all_configured_streams_data: List[Dict[str, str]]
) -> List[StreamInfo]:
    """
    Optimized batch metadata fetching with proper error handling.

    Args:
        live_urls: List of URLs that are live
        all_configured_streams_data: Original stream configuration data

    Returns:
        List of StreamInfo objects with metadata
    """
    url_to_details_map = {s["url"]: s for s in all_configured_streams_data}
    live_streams_info = []
    max_workers = min(config.get_max_workers_metadata(), len(live_urls))

    logger.info("Fetching stream metadata...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit metadata fetch tasks
        future_to_url = {
            executor.submit(get_stream_metadata_json_detailed, url): url
            for url in live_urls
        }

        # Process results as they complete
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result(
                    timeout=config.get_streamlink_timeout_metadata() + 5
                )
                stream_info = _create_stream_info_from_result(
                    url, result, url_to_details_map
                )
                if stream_info:
                    live_streams_info.append(stream_info)
            except Exception as e:
                logger.warning(f"Unexpected error fetching metadata for {url}: {e}")
                # Create basic stream info without metadata
                if url in url_to_details_map:
                    stream_data = url_to_details_map[url]
                    basic_info = StreamInfo(
                        url=url,
                        alias=stream_data.get("alias", "Unnamed"),
                        platform=stream_data.get("platform", "Unknown"),
                        username=stream_data.get("username", "unknown"),
                        category="N/A",
                        status=StreamStatus.LIVE,
                    )
                    live_streams_info.append(basic_info)

    return live_streams_info


def _create_stream_info_from_result(
    url: str, result: "MetadataResult", url_to_details_map: Dict[str, Dict[str, str]]
) -> Optional[StreamInfo]:
    """
    Create StreamInfo object from metadata result.

    Args:
        url: Stream URL
        result: Metadata fetch result
        url_to_details_map: Mapping of URLs to stream configuration

    Returns:
        StreamInfo object or None if creation fails
    """
    if url not in url_to_details_map:
        return None

    stream_data = url_to_details_map[url]

    # Default values
    category = "N/A"
    viewer_count = None
    title = None

    # Extract metadata if successful
    if result.success and result.json_data:
        try:
            import json

            metadata_json = json.loads(result.json_data)
            if "metadata" in metadata_json:
                meta = metadata_json["metadata"]
                title = meta.get("title")

                # Extract viewer count
                for key in ["viewers", "viewer_count", "online"]:
                    if key in meta and meta[key] is not None:
                        try:
                            viewer_count = int(meta[key])
                            if viewer_count >= 0:
                                break
                        except (ValueError, TypeError):
                            continue

                # Extract and sanitize category
                platform = stream_data.get("platform", "Unknown")
                raw_category = extract_category_keywords(
                    (True, result.json_data), platform
                )
                category = sanitize_category_string(raw_category)

        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Could not parse metadata for {url}: {e}")

    return StreamInfo(
        url=url,
        alias=stream_data.get("alias", "Unnamed"),
        platform=stream_data.get("platform", "Unknown"),
        username=stream_data.get("username", "unknown"),
        category=category,
        title=title,
        viewer_count=viewer_count,
        status=StreamStatus.LIVE,
    )


# --- Cache Management Functions ---


def clear_stream_cache() -> int:
    """
    Clear all cached stream status entries.

    Returns:
        Number of entries cleared
    """
    if not config.get_cache_enabled():
        logger.info("Cache is disabled, nothing to clear")
        return 0

    cache = get_cache()
    count = cache.clear()
    logger.info(f"Cleared {count} cached stream status entries")
    return count


def invalidate_stream_cache(url: str) -> bool:
    """
    Invalidate cache entry for a specific stream URL.

    Args:
        url: The stream URL to invalidate

    Returns:
        True if entry was removed, False if not found
    """
    if not config.get_cache_enabled():
        logger.debug("Cache is disabled, nothing to invalidate")
        return False

    cache = get_cache()
    result = cache.invalidate(url)
    if result:
        logger.debug(f"Invalidated cache entry for: {url}")
    return result


def cleanup_expired_cache() -> int:
    """
    Remove expired entries from the stream cache.

    Returns:
        Number of expired entries removed
    """
    if not config.get_cache_enabled():
        return 0

    cache = get_cache()
    count = cache.cleanup_expired()
    if count > 0:
        logger.debug(f"Cleaned up {count} expired cache entries")
    return count


def get_cache_stats() -> Dict[str, int]:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    if not config.get_cache_enabled():
        return {"total_entries": 0, "active_entries": 0, "expired_entries": 0}

    cache = get_cache()
    return cache.get_stats()


# --- Rate Limiting Management Functions ---


def get_rate_limit_status() -> Dict[str, Dict[str, float]]:
    """
    Get rate limiting status for all platforms.

    Returns:
        Dictionary with rate limiting status for global and platform limiters
    """
    if not config.get_rate_limit_enabled():
        return {}

    rate_limiter = get_rate_limiter()
    return rate_limiter.get_status()


def check_rate_limit_available(url: str) -> bool:
    """
    Check if a request can proceed immediately without rate limiting.

    Args:
        url: The stream URL to check

    Returns:
        True if request can proceed immediately, False if rate limited
    """
    if not config.get_rate_limit_enabled():
        return True

    rate_limiter = get_rate_limiter()
    return rate_limiter.try_acquire(url)


def reset_rate_limiters() -> None:
    """
    Reset all rate limiters (mainly for testing and debugging).
    """
    from .rate_limiter import reset_rate_limiter

    reset_rate_limiter()
    logger.info("Reset all rate limiters")


def get_rate_limit_status_message() -> str:
    """
    Get a human-readable rate limit status message for UI display.

    Returns:
        String describing current rate limit status
    """
    if not config.get_rate_limit_enabled():
        return ""

    try:
        status = get_rate_limit_status()
        if not status:
            return ""

        messages = []

        # Global status
        if "global" in status:
            global_status = status["global"]
            utilization = global_status["utilization"]
            if utilization > 0.7:  # High utilization
                messages.append(
                    f"Rate limiting active (Global: {utilization:.0%} used)"
                )

        # Platform status - only show if heavily utilized
        for platform, platform_status in status.items():
            if platform == "global":
                continue
            utilization = platform_status["utilization"]
            if utilization > 0.8:  # Very high utilization
                messages.append(
                    f"{platform.title()}: {utilization:.0%} rate limit used"
                )

        if messages:
            return "⏳ " + ", ".join(messages)

        return ""

    except Exception as e:
        logger.debug(f"Error getting rate limit status message: {e}")
        return ""


# --- Result-based API for improved error handling ---


def check_stream_liveness_safe(url: str) -> StreamResult:
    """
    Check stream liveness using Result pattern for consistent error handling.

    Args:
        url: Stream URL to check

    Returns:
        Result containing StreamCheckResult or error message
    """
    # Validate URL first
    if not url or not isinstance(url, str):
        return Result.Err("Invalid URL provided")

    # Check cache first if enabled
    if config.get_cache_enabled():
        cache = get_cache()
        cached_status = cache.get(url)
        if cached_status is not None:
            logger.debug(f"Using cached status for {url}: {cached_status.value}")
            result = StreamCheckResult(
                is_live=(cached_status == StreamStatus.LIVE), url=url
            )
            return Result.Ok(result)

    # Apply rate limiting
    if config.get_rate_limit_enabled():
        rate_limiter = get_rate_limiter()
        timeout = config.get_streamlink_timeout_liveness()

        if not rate_limiter.acquire(url, timeout=timeout):
            return Result.Err(f"Rate limit exceeded for {url}")

    # Perform the actual check
    check_result = safe_call(_is_stream_live_core, url)

    if check_result.is_err():
        return Result.Err(f"Stream check failed: {check_result.unwrap_err()}")

    result = check_result.unwrap()

    # Update cache if enabled
    if config.get_cache_enabled():
        cache = get_cache()
        status = StreamStatus.LIVE if result.is_live else StreamStatus.OFFLINE
        if result.error and isinstance(result.error, StreamNotFoundError):
            status = StreamStatus.OFFLINE
        elif result.error:
            status = StreamStatus.ERROR

        cache.put(url, status)
        logger.debug(f"Cached status for {url}: {status.value}")

    return Result.Ok(result)


def fetch_stream_metadata_safe(url: str) -> StreamResult:
    """
    Fetch stream metadata using Result pattern for consistent error handling.

    Args:
        url: Stream URL to fetch metadata for

    Returns:
        Result containing MetadataResult or error message
    """
    if not url or not isinstance(url, str):
        return Result.Err("Invalid URL provided")

    # Apply rate limiting
    if config.get_rate_limit_enabled():
        rate_limiter = get_rate_limiter()
        timeout = config.get_streamlink_timeout_metadata()

        if not rate_limiter.acquire(url, timeout=timeout):
            return Result.Err(f"Rate limit exceeded for {url}")

    # Perform the metadata fetch
    metadata_result = safe_call(_get_stream_metadata_core, url)

    if metadata_result.is_err():
        return Result.Err(f"Metadata fetch failed: {metadata_result.unwrap_err()}")

    return Result.Ok(metadata_result.unwrap())


# --- Async API Functions ---


def check_multiple_streams_concurrent(
    urls: List[str],
) -> List[Tuple[str, StreamResult]]:
    """
    Check multiple streams concurrently using async/await.

    Args:
        urls: List of stream URLs to check

    Returns:
        List of (url, result) tuples
    """
    if not urls:
        return []

    try:
        from .async_stream_checker import check_multiple_streams_async

        return asyncio.run(check_multiple_streams_async(urls))
    except Exception as e:
        logger.warning(f"Async concurrent checking failed: {e}")
        # Fallback to synchronous checking
        results = []
        for url in urls:
            result = check_stream_liveness_safe(url)
            results.append((url, result))
        return results


def fetch_live_streams_concurrent(
    all_configured_streams_data: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    Fetch live streams using concurrent async processing.

    Args:
        all_configured_streams_data: List of configured stream dictionaries

    Returns:
        List of live stream info dictionaries
    """
    return fetch_live_streams(all_configured_streams_data, use_async=True)
