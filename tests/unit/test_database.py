"""Tests for the StreamDatabase class."""

from pathlib import Path

import pytest

from src.streamwatch.storage.database import StreamDatabase
from src.streamwatch.core.models import StreamInfo


@pytest.fixture
def db(tmp_path: Path) -> StreamDatabase:
    """Provides an in-memory SQLite database for testing."""
    db_path = tmp_path / "test_streamwatch.db"
    return StreamDatabase(db_path=db_path)


class TestStreamDatabase:
    """Test database operations for streams."""

    def test_save_and_load_streams(self, db: StreamDatabase):
        """Test saving a new stream and loading it back."""
        # Ensure the database is empty initially
        assert db.load_streams() == []

        # Create a new stream object to save
        stream_to_save = StreamInfo(
            url="https://twitch.tv/test_streamer",
            alias="Test Streamer",
            platform="Twitch",
            username="test_streamer",
        )

        # Save the stream
        db.save_stream(stream_to_save)

        # Load streams and verify the saved stream is present
        loaded_streams = db.load_streams()

        assert len(loaded_streams) == 1
        saved_stream = loaded_streams[0]

        # Check that the data was saved and loaded correctly
        assert saved_stream.url == stream_to_save.url
        assert saved_stream.alias == stream_to_save.alias
        assert saved_stream.platform == "Twitch"

    def test_delete_stream(self, db: StreamDatabase):
        """Test saving a stream and then marking it as inactive."""
        stream_to_save = StreamInfo(
            url="https://twitch.tv/to_be_deleted",
            alias="To Be Deleted",
            platform="Twitch",
            username="to_be_deleted",
        )

        # Save and verify it's there
        db.save_stream(stream_to_save)
        assert len(db.load_streams(include_inactive=False)) == 1

        # Delete the stream (marks as inactive)
        was_deleted = db.delete_stream(stream_to_save.url)
        assert was_deleted is True

        # Verify it's no longer loaded by default
        assert len(db.load_streams(include_inactive=False)) == 0

        # Verify it can still be loaded if we include inactive streams
        assert len(db.load_streams(include_inactive=True)) == 1

        # Verify that trying to delete it again returns False
        was_deleted_again = db.delete_stream(stream_to_save.url)
        assert was_deleted_again is False
