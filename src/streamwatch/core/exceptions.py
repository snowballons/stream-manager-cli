"""
StreamWatch Custom Exceptions Module

This module defines custom exception classes for better error handling and categorization
throughout the StreamWatch application, particularly for streamlink-related operations.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StreamlinkError(Exception):
    """
    Base exception class for all streamlink-related errors.

    This serves as the parent class for all specific streamlink error types,
    allowing for broad exception handling when needed.
    """

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        stderr: Optional[str] = None,
        stdout: Optional[str] = None,
        return_code: Optional[int] = None,
    ):
        """
        Initialize StreamlinkError.

        Args:
            message: Human-readable error message
            url: The stream URL that caused the error (if applicable)
            stderr: Standard error output from streamlink command
            stdout: Standard output from streamlink command
            return_code: Process return code from streamlink command
        """
        super().__init__(message)
        self.url = url
        self.stderr = stderr
        self.stdout = stdout
        self.return_code = return_code

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for structured logging/debugging."""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "url": self.url,
            "stderr": self.stderr,
            "stdout": self.stdout,
            "return_code": self.return_code,
        }


class StreamNotFoundError(StreamlinkError):
    """
    Exception raised when a stream is not available or not found.

    This includes cases where:
    - Stream is offline
    - No playable streams found
    - Stream URL is invalid or doesn't exist
    """

    def __init__(self, message: str = "Stream not found or offline", **kwargs: Any):
        super().__init__(message, **kwargs)


class NetworkError(StreamlinkError):
    """
    Exception raised for network-related issues.

    This includes cases where:
    - Network connectivity problems
    - DNS resolution failures
    - Connection timeouts
    - HTTP/HTTPS connection errors
    """

    def __init__(self, message: str = "Network connectivity issue", **kwargs: Any):
        super().__init__(message, **kwargs)


class AuthenticationError(StreamlinkError):
    """
    Exception raised for authentication-related failures.

    This includes cases where:
    - Login credentials are invalid
    - Authentication tokens have expired
    - Access is denied due to subscription requirements
    - Geographic restrictions
    """

    def __init__(self, message: str = "Authentication failed", **kwargs: Any):
        super().__init__(message, **kwargs)


class TimeoutError(StreamlinkError):
    """
    Exception raised when streamlink operations timeout.

    This includes cases where:
    - Command execution exceeds configured timeout
    - Stream loading takes too long
    - Metadata fetching times out
    """

    def __init__(self, message: str = "Operation timed out", **kwargs: Any):
        super().__init__(message, **kwargs)


def categorize_streamlink_error(
    stderr: str, stdout: str, return_code: int, url: Optional[str] = None
) -> StreamlinkError:
    """
    Categorize a streamlink error based on stderr, stdout, and return code.

    This function analyzes the output from a failed streamlink command and
    returns the most appropriate custom exception type.

    Args:
        stderr: Standard error output from streamlink
        stdout: Standard output from streamlink
        return_code: Process return code
        url: The stream URL that was being processed

    Returns:
        StreamlinkError: Appropriate exception subclass based on error analysis
    """
    stderr_lower = stderr.lower() if stderr else ""
    stdout_lower = stdout.lower() if stdout else ""

    # Check for stream not found patterns
    stream_not_found_patterns = [
        "no playable streams found",
        "error: no streams found on",
        "this stream is offline",
        "stream is offline",
        "no streams available",
        "unable to find any streams",
        "stream not found",
        "404 not found",
        "channel not found",
    ]

    for pattern in stream_not_found_patterns:
        if pattern in stderr_lower or pattern in stdout_lower:
            return StreamNotFoundError(
                f"Stream not available: {pattern}",
                url=url,
                stderr=stderr,
                stdout=stdout,
                return_code=return_code,
            )

    # Check for network-related errors
    network_error_patterns = [
        "connection refused",
        "connection timed out",
        "network is unreachable",
        "temporary failure in name resolution",
        "could not resolve host",
        "connection reset by peer",
        "ssl certificate verify failed",
        "ssl handshake failed",
        "unable to connect",
        "connection error",
        "network error",
        "dns resolution failed",
    ]

    for pattern in network_error_patterns:
        if pattern in stderr_lower or pattern in stdout_lower:
            return NetworkError(
                f"Network connectivity issue: {pattern}",
                url=url,
                stderr=stderr,
                stdout=stdout,
                return_code=return_code,
            )

    # Check for authentication errors
    auth_error_patterns = [
        "authentication failed",
        "login failed",
        "invalid credentials",
        "access denied",
        "unauthorized",
        "forbidden",
        "subscription required",
        "premium account required",
        "geo-blocked",
        "not available in your region",
        "region blocked",
        "authentication required",
    ]

    for pattern in auth_error_patterns:
        if pattern in stderr_lower or pattern in stdout_lower:
            return AuthenticationError(
                f"Authentication issue: {pattern}",
                url=url,
                stderr=stderr,
                stdout=stdout,
                return_code=return_code,
            )

    # Check for timeout-related errors (this should be handled by subprocess.TimeoutExpired,
    # but we include it here for completeness)
    timeout_patterns = ["timed out", "timeout", "operation timeout", "request timeout"]

    for pattern in timeout_patterns:
        if pattern in stderr_lower or pattern in stdout_lower:
            return TimeoutError(
                f"Operation timed out: {pattern}",
                url=url,
                stderr=stderr,
                stdout=stdout,
                return_code=return_code,
            )

    # Default to generic StreamlinkError if no specific pattern matches
    return StreamlinkError(
        f"Streamlink command failed with return code {return_code}",
        url=url,
        stderr=stderr,
        stdout=stdout,
        return_code=return_code,
    )


class RateLimitExceededError(StreamlinkError):
    """
    Exception raised when rate limiting prevents a request from proceeding.

    This exception is raised when the rate limiter determines that too many
    requests have been made and the request should be delayed or skipped.
    """

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        platform: Optional[str] = None,
        retry_after: Optional[float] = None,
    ):
        """
        Initialize RateLimitExceededError.

        Args:
            message: Human-readable error message
            url: The stream URL that was rate limited
            platform: The platform that was rate limited
            retry_after: Suggested time to wait before retrying (seconds)
        """
        super().__init__(message, url=url)
        self.platform = platform
        self.retry_after = retry_after

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for structured logging/debugging."""
        result = super().to_dict()
        result.update({"platform": self.platform, "retry_after": self.retry_after})
        return result
