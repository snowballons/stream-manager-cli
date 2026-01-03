from unittest.mock import Mock, patch


from src.streamwatch import player


class TestPlayerLaunching:
    @patch("src.streamwatch.player.subprocess.Popen")
    @patch("src.streamwatch.player.config")
    def test_launch_player_success(self, mock_config, mock_popen):
        """Test successful player launch."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        process = player.launch_player_process("https://test.tv/user", "best")
        assert process is not None
        mock_popen.assert_called_once()

    @patch("src.streamwatch.player.subprocess.Popen")
    def test_launch_player_failure(self, mock_popen):
        """Test player launch failure handling."""
        mock_popen.side_effect = FileNotFoundError("Player not found")

        process = player.launch_player_process("https://test.tv/user", "best")
        assert process is None

    def test_terminate_player_process(self):
        """Test terminating a player process."""
        mock_process = Mock()
        mock_process.poll.return_value = None

        player.terminate_player_process(mock_process)
        mock_process.terminate.assert_called_once()

    def test_terminate_already_finished_process(self):
        """Test terminating an already finished process."""
        mock_process = Mock()
        mock_process.poll.return_value = 0  # Already finished

        # Should not raise an exception
        player.terminate_player_process(mock_process)
        mock_process.terminate.assert_not_called()
