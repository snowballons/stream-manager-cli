"""Tests for the StreamManager class."""

from unittest.mock import MagicMock, patch

import pytest

from src.streamwatch.core.models import StreamInfo
from src.streamwatch.stream.manager import StreamManager


# Mock the database dependency for all tests in this class
@pytest.fixture
def mock_db():
    """Provides a mock database object."""
    return MagicMock()


@pytest.fixture
def manager(mock_db):
    """Provides a StreamManager instance with a mocked database."""
    return StreamManager(database=mock_db)


class TestStreamManager:
    """Test StreamManager functionality with mocked dependencies."""

    @patch("src.streamwatch.stream.manager.ui")
    def test_add_streams_success(self, mock_ui, manager, mock_db):
        """Test successful stream addition delegation."""
        mock_ui.prompt_add_streams.return_value = [
            {"url": "https://twitch.tv/test", "alias": "Test"}
        ]

        success, message = manager.add_streams()

        assert success is True
        assert "Successfully added 1 new stream(s)" in message
        mock_ui.prompt_add_streams.assert_called_once()
        mock_db.save_stream.assert_called_once()

    @patch("src.streamwatch.stream.manager.ui")
    def test_add_streams_cancelled(self, mock_ui, manager):
        """Test cancelled stream addition."""
        mock_ui.prompt_add_streams.return_value = []

        success, message = manager.add_streams()

        assert success is False
        assert "cancelled" in message

    @patch("src.streamwatch.stream.manager.ui")
    def test_remove_streams_success(self, mock_ui, manager, mock_db):
        """Test successful stream removal delegation."""
        mock_stream = StreamInfo(url="https://twitch.tv/test", alias="Test")
        mock_db.load_streams.return_value = [mock_stream]
        mock_db.delete_stream.return_value = True
        mock_ui.prompt_remove_streams_dialog.return_value = [0]

        success, message = manager.remove_streams()

        assert success is True
        assert "Successfully removed 1 stream(s)" in message
        mock_db.load_streams.assert_called_once()
        mock_db.delete_stream.assert_called_with("https://twitch.tv/test")

    @patch("src.streamwatch.stream.manager.ui")
    def test_list_streams(self, mock_ui, manager, mock_db):
        """Test listing streams delegation."""
        mock_db.load_streams.return_value = []

        manager.list_streams()

        mock_db.load_streams.assert_called_once()
        mock_ui.display_stream_list.assert_called_once()

    def test_load_streams(self, manager, mock_db):
        """Test loading streams from the database."""
        mock_stream = StreamInfo(url="https://twitch.tv/test", alias="Test")
        mock_db.load_streams.return_value = [mock_stream]

        result = manager.load_streams()

        assert len(result) == 1
        assert result[0]["alias"] == "Test"
        mock_db.load_streams.assert_called_once()
