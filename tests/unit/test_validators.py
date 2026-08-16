"""Tests for the validators module."""

import pytest

from src.streamwatch.validation.validators import (
    SecurityError,
    ValidationError,
    sanitize_html,
    validate_alias,
    validate_category,
    validate_url,
    validate_username,
    validate_viewer_count,
)


class TestValidators:
    """Test input validation functions."""

    def test_validate_url_valid_twitch(self):
        """Test validating a valid Twitch URL."""
        is_valid, sanitized_url, metadata = validate_url(
            "https://www.twitch.tv/testuser"
        )
        assert is_valid is True
        assert sanitized_url == "https://www.twitch.tv/testuser"
        assert metadata["platform"] == "Twitch"
        assert metadata["username"] == "testuser"

    def test_validate_url_valid_youtube(self):
        """Test validating a valid YouTube URL."""
        is_valid, sanitized_url, metadata = validate_url(
            "https://www.youtube.com/@testchannel"
        )
        assert is_valid is True
        assert metadata["platform"] == "YouTube"
        assert metadata["username"] == "testchannel"

    def test_validate_url_invalid(self):
        """Test validating an invalid URL."""
        with pytest.raises(ValidationError):
            validate_url("not-a-url")

    def test_validate_url_dangerous_javascript(self):
        """Test rejecting dangerous JavaScript URLs."""
        with pytest.raises(SecurityError):
            validate_url("javascript:alert('xss')")

    def test_validate_alias_valid(self):
        """Test validating a valid alias."""
        result = validate_alias("Test Stream 123")
        assert result == "Test Stream 123"

    def test_validate_alias_empty(self):
        """Test rejecting empty alias."""
        with pytest.raises(ValidationError):
            validate_alias("")

    def test_validate_alias_too_long(self):
        """Test rejecting alias that's too long."""
        long_alias = "a" * 201  # MAX_ALIAS_LENGTH is 200
        with pytest.raises(ValidationError):
            validate_alias(long_alias)

    def test_validate_username_valid(self):
        """Test validating a valid username."""
        result = validate_username("test_user123")
        assert result == "test_user123"

    def test_validate_username_with_at_symbol(self):
        """Test username with @ symbol gets cleaned."""
        result = validate_username("@testuser")
        assert result == "testuser"

    def test_validate_category_valid(self):
        """Test validating a valid category."""
        result = validate_category("Gaming & Entertainment")
        assert result == "Gaming &amp; Entertainment"

    def test_validate_viewer_count_valid_int(self):
        """Test validating a valid integer viewer count."""
        result = validate_viewer_count(1234)
        assert result == 1234

    def test_validate_viewer_count_valid_string(self):
        """Test validating a valid string viewer count."""
        result = validate_viewer_count("1234")
        assert result == 1234

    def test_validate_viewer_count_negative(self):
        """Test rejecting negative viewer count."""
        with pytest.raises(ValidationError):
            validate_viewer_count(-1)

    def test_validate_viewer_count_none(self):
        """Test handling None viewer count."""
        result = validate_viewer_count(None)
        assert result is None

    def test_sanitize_html_basic(self):
        """Test basic HTML sanitization."""
        result = sanitize_html("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "Hello" in result

    def test_sanitize_html_safe_content(self):
        """Test that safe content passes through."""
        safe_text = "This is safe content 123"
        result = sanitize_html(safe_text)
        assert result == safe_text
