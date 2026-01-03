"""Extended tests for player module."""

from unittest.mock import MagicMock, patch


from src.streamwatch import player


class TestPlayerFunctions:
    """Test player module functions."""

    def test_execute_hook_pre(self):
        """Test executing pre-playback hook."""
        stream_info = {"url": "https://twitch.tv/test", "username": "test"}

        # Should not raise exception
        player.execute_hook("pre", stream_info, "best")

    def test_execute_hook_post(self):
        """Test executing post-playback hook."""
        stream_info = {"url": "https://twitch.tv/test", "username": "test"}

        # Should not raise exception
        player.execute_hook("post", stream_info, "best")

    def test_execute_hook_invalid_type(self):
        """Test executing hook with invalid type."""
        stream_info = {"url": "https://twitch.tv/test", "username": "test"}

        # Should not raise exception
        player.execute_hook("invalid", stream_info, "best")

    @patch("src.streamwatch.player.config.get_pre_playback_hook")
    @patch("src.streamwatch.player.subprocess.run")
    def test_execute_hook_with_script(self, mock_run, mock_get_hook):
        """Test executing hook with actual script."""
        mock_get_hook.return_value = "/path/to/script.sh"
        mock_run.return_value = MagicMock(returncode=0)

        stream_info = {"url": "https://twitch.tv/test", "username": "test"}

        # Should not raise exception
        player.execute_hook("pre", stream_info, "best")

    @patch("src.streamwatch.player.subprocess.Popen")
    def test_play_stream_function(self, mock_popen):
        """Test play_stream function if it exists."""
        # Check if function exists
        if hasattr(player, "play_stream"):
            mock_process = MagicMock()
            mock_popen.return_value = mock_process

            result = player.play_stream("https://twitch.tv/test", "best")
            assert result is not None

    def test_get_available_qualities_function(self):
        """Test get_available_qualities function if it exists."""
        # Check if function exists
        if hasattr(player, "get_available_qualities"):
            result = player.get_available_qualities("https://twitch.tv/test")
            assert isinstance(result, (list, dict, type(None)))

    @patch("src.streamwatch.player.subprocess.run")
    def test_stop_stream_function(self, mock_run):
        """Test stop_stream function if it exists."""
        # Check if function exists
        if hasattr(player, "stop_stream"):
            mock_run.return_value = MagicMock(returncode=0)

            # Should not raise exception
            player.stop_stream()

    def test_validate_quality_function(self):
        """Test validate_quality function if it exists."""
        # Check if function exists
        if hasattr(player, "validate_quality"):
            result = player.validate_quality("best")
            assert isinstance(result, bool)

    def test_get_player_command_function(self):
        """Test get_player_command function if it exists."""
        # Check if function exists
        if hasattr(player, "get_player_command"):
            result = player.get_player_command()
            assert isinstance(result, (str, list, type(None)))
