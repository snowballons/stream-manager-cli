"""Unit tests for UI components module."""

from unittest.mock import patch


from src.streamwatch.ui import display, input_handler

# We now test display and input_handler separately


class TestDisplayFunctions:
    """Test screen management and display functionality."""

    @patch("src.streamwatch.ui.display.subprocess.run")
    def test_clear_screen(self, mock_run):
        """Test screen clearing."""
        display.clear_screen()
        mock_run.assert_called_once()

    def test_format_viewer_count(self):
        """Test viewer count formatting."""
        assert display.format_viewer_count(123) == "123"
        assert display.format_viewer_count(1234) == "1.2K"
        assert display.format_viewer_count(1234567) == "1.2M"
        assert display.format_viewer_count(None) == ""


class TestInputFunctions:
    """Test user input and prompting functionality."""

    @patch("src.streamwatch.ui.input_handler.prompt")
    def test_prompt_for_filepath_success(self, mock_prompt):
        """Test successful file path prompting."""
        mock_prompt.return_value = "/path/to/file.txt"
        result = input_handler.prompt_for_filepath("Enter file path: ")
        assert result == "/path/to/file.txt"

    @patch("src.streamwatch.ui.input_handler.radiolist_dialog")
    def test_select_stream_dialog_success(self, mock_dialog):
        """Test successful stream selection."""
        mock_stream = {"url": "test_url", "alias": "Test"}
        mock_dialog.return_value.run.return_value = mock_stream

        result = input_handler.select_stream_dialog([mock_stream])
        assert result == mock_stream
