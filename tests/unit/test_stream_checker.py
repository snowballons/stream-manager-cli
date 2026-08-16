from unittest.mock import patch


from src.streamwatch.stream.checker import _is_stream_live_core


class TestStreamLivenessChecking:
    @patch("src.streamwatch.stream.checker.subprocess.run")
    def test_is_stream_live_success(self, mock_run):
        """Test successful stream liveness check."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Available streams: best"
        mock_run.return_value.stderr = ""

        result = _is_stream_live_core("https://test.tv/user")
        assert result.is_live is True
        assert result.url == "https://test.tv/user"
        assert result.error is None

    @patch("src.streamwatch.stream.checker.subprocess.run")
    def test_is_stream_live_offline(self, mock_run):
        """Test stream offline detection."""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "No streams found"

        result = _is_stream_live_core("https://test.tv/offline_user")
        assert result.is_live is False
        assert result.url == "https://test.tv/offline_user"
        assert result.error is not None

    @patch("src.streamwatch.stream.checker.subprocess.run")
    def test_is_stream_live_timeout(self, mock_run):
        """Test stream check timeout handling."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("streamlink", 10)

        result = _is_stream_live_core("https://test.tv/timeout_user")
        assert result.is_live is False
        assert result.error is not None
        assert "timeout" in str(result.error).lower()
