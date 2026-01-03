"""Unit tests for configuration management module."""

from unittest.mock import patch


from src.streamwatch import config


class TestConfigManagement:
    """Test configuration loading and management."""

    def test_default_config_values(self):
        """Test that default configuration values are properly defined."""
        assert "Streamlink" in config.DEFAULT_CONFIG
        assert config.DEFAULT_CONFIG["Streamlink"]["quality"] == "best"

    def test_get_streamlink_quality_default(self):
        """Test getting streamlink quality with default value."""
        with patch.object(config.config_parser, "get", return_value="best"):
            quality = config.get_streamlink_quality()
            assert quality == "best"

    def test_config_parsing_with_custom_values(self, tmp_path):
        """Test config parsing with custom values."""
        config_content = "[Streamlink]\nquality = 720p\n"
        config_file = tmp_path / "config.ini"
        config_file.write_text(config_content)

        with patch.object(config, "CONFIG_FILE_PATH", config_file):
            config.load_config()  # Force reload
            assert config.get_streamlink_quality() == "720p"
