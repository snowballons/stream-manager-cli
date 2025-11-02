"""
Test utilities and fixtures for StreamWatch tests.

Provides common test data, mocks, and utilities to improve
test coverage and reduce test code duplication.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock

import pytest

from src.streamwatch.models import StreamInfo, StreamStatus
from src.streamwatch.result import Result


class MockStreamChecker:
    """Mock stream checker for testing."""

    def __init__(self, live_urls: List[str] = None):
        self.live_urls = live_urls or []

    def check_stream_liveness(self, url: str) -> Result:
        """Mock stream liveness check."""
        if url in self.live_urls:
            return Result.Ok(Mock(is_live=True, url=url, error=None))
        return Result.Ok(Mock(is_live=False, url=url, error=None))


class MockDatabase:
    """Mock database for testing."""

    def __init__(self):
        self.streams: List[StreamInfo] = []
        self.closed = False

    def save_stream(self, stream: StreamInfo) -> None:
        """Mock save stream."""
        # Remove existing stream with same URL
        self.streams = [s for s in self.streams if s.url != stream.url]
        self.streams.append(stream)

    def load_streams(self, include_inactive: bool = False) -> List[StreamInfo]:
        """Mock load streams."""
        return self.streams.copy()

    def delete_stream(self, url: str) -> bool:
        """Mock delete stream."""
        original_count = len(self.streams)
        self.streams = [s for s in self.streams if s.url != url]
        return len(self.streams) < original_count

    def close(self) -> None:
        """Mock close."""
        self.closed = True


@pytest.fixture
def temp_config_dir():
    """Provide temporary config directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_streams() -> List[Dict[str, str]]:
    """Provide sample stream data for tests."""
    return [
        {
            "url": "https://www.twitch.tv/testuser1",
            "alias": "Test User 1",
            "platform": "Twitch",
            "username": "testuser1",
        },
        {
            "url": "https://www.youtube.com/@testchannel",
            "alias": "Test Channel",
            "platform": "YouTube",
            "username": "testchannel",
        },
        {
            "url": "https://kick.com/teststreamer",
            "alias": "Test Streamer",
            "platform": "Kick",
            "username": "teststreamer",
        },
    ]


@pytest.fixture
def sample_stream_info() -> List[StreamInfo]:
    """Provide sample StreamInfo objects for tests."""
    return [
        StreamInfo(
            url="https://www.twitch.tv/testuser1",
            alias="Test User 1",
            platform="Twitch",
            username="testuser1",
            category="Gaming",
            status=StreamStatus.LIVE,
            viewer_count=1234,
        ),
        StreamInfo(
            url="https://www.youtube.com/@testchannel",
            alias="Test Channel",
            platform="YouTube",
            username="testchannel",
            category="Technology",
            status=StreamStatus.OFFLINE,
        ),
    ]


@pytest.fixture
def mock_subprocess_success():
    """Mock successful subprocess run."""
    mock = Mock()
    mock.returncode = 0
    mock.stdout = "Available streams: best, worst"
    mock.stderr = ""
    return mock


@pytest.fixture
def mock_subprocess_failure():
    """Mock failed subprocess run."""
    mock = Mock()
    mock.returncode = 1
    mock.stdout = ""
    mock.stderr = "error: No plugin can handle URL"
    return mock


def create_mock_config(**overrides) -> Mock:
    """Create mock configuration with default values."""
    defaults = {
        "get_cache_enabled": lambda: True,
        "get_rate_limit_enabled": lambda: True,
        "get_streamlink_timeout_liveness": lambda: 10,
        "get_streamlink_timeout_metadata": lambda: 15,
        "get_max_workers_liveness": lambda: 4,
        "get_max_workers_metadata": lambda: 2,
        "get_twitch_disable_ads": lambda: True,
    }

    config = Mock()
    for key, value in {**defaults, **overrides}.items():
        setattr(config, key, value)

    return config


def assert_result_ok(result: Result, expected_value: Any = None) -> None:
    """Assert that Result is Ok with optional value check."""
    assert (
        result.is_ok()
    ), f"Expected Ok result, got Err: {result.unwrap_err() if result.is_err() else 'N/A'}"
    if expected_value is not None:
        assert result.unwrap() == expected_value


def assert_result_err(result: Result, expected_error: str = None) -> None:
    """Assert that Result is Err with optional error message check."""
    assert (
        result.is_err()
    ), f"Expected Err result, got Ok: {result.unwrap() if result.is_ok() else 'N/A'}"
    if expected_error is not None:
        assert expected_error in str(result.unwrap_err())


class TestDataFactory:
    """Factory for creating test data objects."""

    @staticmethod
    def create_stream_info(
        url: str = "https://www.twitch.tv/test", alias: str = "Test Stream", **kwargs
    ) -> StreamInfo:
        """Create StreamInfo with defaults."""
        defaults = {
            "platform": "Twitch",
            "username": "test",
            "category": "Gaming",
            "status": StreamStatus.UNKNOWN,
        }

        return StreamInfo(url=url, alias=alias, **{**defaults, **kwargs})

    @staticmethod
    def create_stream_dict(
        url: str = "https://www.twitch.tv/test", alias: str = "Test Stream", **kwargs
    ) -> Dict[str, str]:
        """Create stream dictionary with defaults."""
        defaults = {"platform": "Twitch", "username": "test"}

        return {"url": url, "alias": alias, **{**defaults, **kwargs}}
