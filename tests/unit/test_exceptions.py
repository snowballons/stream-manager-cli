"""Tests for exceptions module."""

from src.streamwatch.core.exceptions import (
    AuthenticationError,
    NetworkError,
    RateLimitExceededError,
    StreamlinkError,
    StreamNotFoundError,
    TimeoutError,
)


class TestStreamlinkError:
    """Test StreamlinkError base exception."""

    def test_basic_creation(self):
        """Test creating basic StreamlinkError."""
        error = StreamlinkError("Test error")

        assert str(error) == "Test error"
        assert error.url is None
        assert error.stderr is None
        assert error.stdout is None
        assert error.return_code is None

    def test_full_creation(self):
        """Test creating StreamlinkError with all parameters."""
        error = StreamlinkError(
            message="Test error",
            url="https://twitch.tv/test",
            stderr="Error output",
            stdout="Normal output",
            return_code=1,
        )

        assert str(error) == "Test error"
        assert error.url == "https://twitch.tv/test"
        assert error.stderr == "Error output"
        assert error.stdout == "Normal output"
        assert error.return_code == 1

    def test_to_dict(self):
        """Test converting error to dictionary."""
        error = StreamlinkError(
            message="Test error",
            url="https://twitch.tv/test",
            stderr="Error output",
            return_code=1,
        )

        result = error.to_dict()

        assert result["error_type"] == "StreamlinkError"
        assert result["message"] == "Test error"
        assert result["url"] == "https://twitch.tv/test"
        assert result["stderr"] == "Error output"
        assert result["return_code"] == 1


class TestStreamNotFoundError:
    """Test StreamNotFoundError exception."""

    def test_creation(self):
        """Test creating StreamNotFoundError."""
        error = StreamNotFoundError("Stream not found", url="https://twitch.tv/test")

        assert str(error) == "Stream not found"
        assert error.url == "https://twitch.tv/test"
        assert isinstance(error, StreamlinkError)

    def test_to_dict(self):
        """Test converting to dictionary."""
        error = StreamNotFoundError("Stream not found", url="https://twitch.tv/test")
        result = error.to_dict()

        assert result["error_type"] == "StreamNotFoundError"


class TestStreamOfflineError:
    """Test TimeoutError exception."""

    def test_creation(self):
        """Test creating TimeoutError."""
        error = TimeoutError("Stream timeout", url="https://twitch.tv/test")

        assert str(error) == "Stream timeout"
        assert error.url == "https://twitch.tv/test"
        assert isinstance(error, StreamlinkError)


class TestUnsupportedPlatformError:
    """Test AuthenticationError exception."""

    def test_creation(self):
        """Test creating AuthenticationError."""
        error = AuthenticationError("Auth failed", url="https://example.com/test")

        assert str(error) == "Auth failed"
        assert error.url == "https://example.com/test"
        assert isinstance(error, StreamlinkError)


class TestNetworkError:
    """Test NetworkError exception."""

    def test_creation(self):
        """Test creating NetworkError."""
        error = NetworkError("Network error", url="https://twitch.tv/test")

        assert str(error) == "Network error"
        assert error.url == "https://twitch.tv/test"
        assert isinstance(error, StreamlinkError)


class TestPlayerError:
    """Test RateLimitExceededError exception."""

    def test_creation(self):
        """Test creating RateLimitExceededError."""
        error = RateLimitExceededError("Rate limited", url="https://twitch.tv/test")

        assert str(error) == "Rate limited"
        assert error.url == "https://twitch.tv/test"
        assert isinstance(error, StreamlinkError)

    def test_with_platform_and_retry_after(self):
        """Test creating RateLimitExceededError with platform and retry_after."""
        error = RateLimitExceededError(
            "Rate limited",
            url="https://twitch.tv/test",
            platform="Twitch",
            retry_after=60.0,
        )

        assert error.platform == "Twitch"
        assert error.retry_after == 60.0

    def test_to_dict(self):
        """Test converting to dictionary."""
        error = RateLimitExceededError(
            "Rate limited",
            url="https://twitch.tv/test",
            platform="Twitch",
            retry_after=60.0,
        )
        result = error.to_dict()

        assert result["error_type"] == "RateLimitExceededError"
        assert result["platform"] == "Twitch"
        assert result["retry_after"] == 60.0


class TestConfigurationError:
    """Test NetworkError exception (additional tests)."""

    def test_creation(self):
        """Test creating NetworkError."""
        error = NetworkError("Network error")

        assert str(error) == "Network error"
        assert isinstance(error, StreamlinkError)


class TestRateLimitError:
    """Test AuthenticationError exception (additional tests)."""

    def test_creation(self):
        """Test creating AuthenticationError."""
        error = AuthenticationError("Auth error")

        assert str(error) == "Auth error"
        assert isinstance(error, StreamlinkError)


class TestCircuitBreakerError:
    """Test TimeoutError exception (additional tests)."""

    def test_creation(self):
        """Test creating TimeoutError."""
        error = TimeoutError("Timeout error")

        assert str(error) == "Timeout error"
        assert isinstance(error, StreamlinkError)
