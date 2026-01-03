from unittest.mock import Mock, patch


from src.streamwatch.playback_controller import PlaybackController


class TestPlaybackController:
    @patch("src.streamwatch.playback_controller.player")
    def test_stop_playback(self, mock_player):
        """Test stopping playback."""
        pc = PlaybackController()
        mock_process = Mock()
        pc.stop_playback(mock_process, {}, "best")
        mock_player.terminate_player_process.assert_called_with(mock_process)
