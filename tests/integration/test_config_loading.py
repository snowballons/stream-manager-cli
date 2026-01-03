"""Integration tests for configuration loading and management."""

from unittest.mock import patch


from src.streamwatch import config


class TestConfigurationIntegration:
    """Test configuration loading and integration."""

    def test_config_file_creation_and_defaults(self, tmp_path):
        """Test that a default config file is created and values are correct."""
        config_dir = tmp_path / "streamwatch"
        config_file = config_dir / "config.ini"

        # Patch the config path to use our temporary directory
        with patch.object(config, "CONFIG_FILE_PATH", config_file), patch.object(
            config, "USER_CONFIG_DIR", config_dir
        ):
            # This should create the file
            config.load_config()

            # Verify the file was created
            assert config_file.exists()

            # Verify we can read default values
            assert config.get_streamlink_quality() == "best"
            assert config.get_max_workers_liveness() == 4
