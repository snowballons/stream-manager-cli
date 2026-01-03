"""Tests for the models module."""

import pytest

from src.streamwatch.models import (
    PlaybackSession,
    StreamInfo,
    StreamStatus,
    UrlMetadata,
    UrlType,
)


class TestStreamInfo:
    """Test StreamInfo model validation and functionality."""

    def test_create_valid_stream_info(self):
        """Test creating a valid StreamInfo object."""
        stream = StreamInfo(
            url="https://www.twitch.tv/testuser",
            alias="Test User",
            platform="Twitch",
            username="testuser",
            category="Gaming",
            viewer_count=1234,
            status=StreamStatus.LIVE,
        )

        assert stream.url == "https://www.twitch.tv/testuser"
        assert stream.alias == "Test User"
        assert stream.platform == "Twitch"
        assert stream.username == "testuser"
        assert stream.category == "Gaming"
        assert stream.viewer_count == 1234
        assert stream.status == StreamStatus.LIVE

    def test_stream_info_to_dict(self):
        """Test converting StreamInfo to dictionary."""
        stream = StreamInfo(url="https://www.twitch.tv/testuser", alias="Test User")

        result = stream.to_dict()
        assert isinstance(result, dict)
        assert result["url"] == "https://www.twitch.tv/testuser"
        assert result["alias"] == "Test User"

    def test_stream_info_from_dict(self):
        """Test creating StreamInfo from dictionary."""
        data = {
            "url": "https://www.twitch.tv/testuser",
            "alias": "Test User",
            "platform": "Twitch",
            "username": "testuser",
        }

        stream = StreamInfo.from_dict(data)
        assert stream.url == "https://www.twitch.tv/testuser"
        assert stream.alias == "Test User"

    def test_stream_info_invalid_url(self):
        """Test StreamInfo validation with invalid URL."""
        with pytest.raises(ValueError):
            StreamInfo(url="not-a-url", alias="Test User")

    def test_stream_info_negative_viewer_count(self):
        """Test StreamInfo validation with negative viewer count."""
        with pytest.raises(ValueError):
            StreamInfo(
                url="https://www.twitch.tv/testuser", alias="Test User", viewer_count=-1
            )


class TestUrlMetadata:
    """Test UrlMetadata model."""

    def test_create_url_metadata(self):
        """Test creating UrlMetadata object."""
        metadata = UrlMetadata(
            platform="Twitch", username="testuser", url_type=UrlType.CHANNEL
        )

        assert metadata.platform == "Twitch"
        assert metadata.username == "testuser"
        assert metadata.url_type == UrlType.CHANNEL

    def test_url_metadata_to_dict(self):
        """Test converting UrlMetadata to dictionary."""
        metadata = UrlMetadata(platform="Twitch", username="testuser")

        result = metadata.to_dict()
        assert result["platform"] == "Twitch"
        assert result["username"] == "testuser"


class TestPlaybackSession:
    """Test PlaybackSession model."""

    def test_create_playback_session(self):
        """Test creating a PlaybackSession object."""
        stream = StreamInfo(url="https://www.twitch.tv/testuser", alias="Test User")

        session = PlaybackSession(
            current_stream=stream, current_quality="best", all_live_streams=[stream]
        )

        assert session.current_stream == stream
        assert session.current_quality == "best"
        assert len(session.all_live_streams) == 1
        assert session.current_index == 0

    def test_playback_session_get_next_stream(self):
        """Test getting next stream in playback session."""
        stream1 = StreamInfo(url="https://www.twitch.tv/user1", alias="User 1")
        stream2 = StreamInfo(url="https://www.twitch.tv/user2", alias="User 2")

        session = PlaybackSession(
            current_stream=stream1,
            current_quality="best",
            all_live_streams=[stream1, stream2],
            current_index=0,
        )

        next_stream = session.get_next_stream()
        assert next_stream == stream2

    def test_playback_session_get_previous_stream(self):
        """Test getting previous stream in playback session."""
        stream1 = StreamInfo(url="https://www.twitch.tv/user1", alias="User 1")
        stream2 = StreamInfo(url="https://www.twitch.tv/user2", alias="User 2")

        session = PlaybackSession(
            current_stream=stream2,
            current_quality="best",
            all_live_streams=[stream1, stream2],
            current_index=1,
        )

        prev_stream = session.get_previous_stream()
        assert prev_stream == stream1


class TestStreamStatus:
    """Test StreamStatus enum."""

    def test_stream_status_values(self):
        """Test StreamStatus enum values."""
        assert StreamStatus.LIVE.value == "live"
        assert StreamStatus.OFFLINE.value == "offline"
        assert StreamStatus.UNKNOWN.value == "unknown"
        assert StreamStatus.ERROR.value == "error"

    def test_stream_status_string_conversion(self):
        """Test StreamStatus string conversion."""
        assert str(StreamStatus.LIVE) == "live"
        assert str(StreamStatus.OFFLINE) == "offline"
