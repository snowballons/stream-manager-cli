"""Extended tests for stream_utils module."""

from src.streamwatch.stream_utils import parse_url_metadata, parse_url_metadata_typed


class TestParseUrlMetadataExtended:
    """Extended tests for URL parsing functionality."""

    def test_parse_twitch_url(self):
        """Test parsing Twitch URL."""
        result = parse_url_metadata("https://twitch.tv/testuser")
        assert result["platform"] == "Twitch"
        assert result["username"] == "testuser"

    def test_parse_kick_url(self):
        """Test parsing Kick URL."""
        result = parse_url_metadata("https://kick.com/testuser")
        assert result["platform"] == "Kick"
        assert result["username"] == "testuser"

    def test_parse_invalid_url(self):
        """Test parsing invalid URL."""
        result = parse_url_metadata("not_a_url")
        assert result["platform"] == "Unknown"
        assert result["username"] == "unknown_stream"

    def test_parse_empty_url(self):
        """Test parsing empty URL."""
        result = parse_url_metadata("")
        assert result["platform"] == "Unknown"
        assert result["username"] == "unknown_stream"

    def test_parse_none_url(self):
        """Test parsing None URL."""
        result = parse_url_metadata(None)
        assert result["platform"] == "Unknown"
        assert result["username"] == "unknown_stream"

    def test_parse_generic_url(self):
        """Test parsing generic URL."""
        result = parse_url_metadata("https://example.com/stream")
        assert result["platform"] == "example"  # Fixed expectation
        assert result["username"] == "stream"

    def test_parse_url_metadata_typed_youtube(self):
        """Test typed URL parsing for YouTube."""
        result = parse_url_metadata_typed("https://youtube.com/@testchannel")
        assert result.platform == "Youtube"  # Fixed expectation
        assert result.username == "testchannel"

    def test_parse_url_metadata_typed_invalid(self):
        """Test typed URL parsing for invalid URL."""
        result = parse_url_metadata_typed("invalid")
        assert result.platform == "Unknown"
        assert result.username == "unknown_stream"
