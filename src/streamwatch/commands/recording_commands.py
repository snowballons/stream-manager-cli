"""Recording-related commands for StreamWatch."""

import logging
from typing import Any, Dict

from ..recording import recording_manager
from .base import Command, CommandResult

logger = logging.getLogger("streamwatch.commands.recording")


class StartRecordingCommand(Command):
    """Command to start recording a stream."""

    def __init__(self, url: str, stream_info: Dict[str, Any]):
        self.url = url
        self.stream_info = stream_info

    def execute(self) -> CommandResult:
        """Execute the start recording command."""
        try:
            success = recording_manager.start_recording(self.url, self.stream_info)

            if success:
                username = self.stream_info.get("username", "Unknown")
                platform = self.stream_info.get("platform", "Unknown")
                return CommandResult(
                    success=True,
                    message=f"Started recording {username} on {platform}",
                    data={"recording_id": f"{platform}_{username}"},
                )
            else:
                return CommandResult(success=False, message="Failed to start recording")

        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            return CommandResult(
                success=False, message=f"Error starting recording: {str(e)}"
            )


class StopRecordingCommand(Command):
    """Command to stop a recording."""

    def __init__(self, recording_id: str):
        self.recording_id = recording_id

    def execute(self) -> CommandResult:
        """Execute the stop recording command."""
        try:
            success = recording_manager.stop_recording(self.recording_id)

            if success:
                return CommandResult(
                    success=True, message=f"Stopped recording {self.recording_id}"
                )
            else:
                return CommandResult(
                    success=False,
                    message=f"No active recording found for {self.recording_id}",
                )

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return CommandResult(
                success=False, message=f"Error stopping recording: {str(e)}"
            )


class ListRecordingsCommand(Command):
    """Command to list active recordings."""

    def execute(self) -> CommandResult:
        """Execute the list recordings command."""
        try:
            active_recordings = recording_manager.get_active_recordings()

            return CommandResult(
                success=True,
                message=f"Found {len(active_recordings)} active recordings",
                data={"recordings": active_recordings},
            )

        except Exception as e:
            logger.error(f"Error listing recordings: {e}")
            return CommandResult(
                success=False, message=f"Error listing recordings: {str(e)}"
            )


class StopAllRecordingsCommand(Command):
    """Command to stop all active recordings."""

    def execute(self) -> CommandResult:
        """Execute the stop all recordings command."""
        try:
            recording_manager.stop_all_recordings()

            return CommandResult(success=True, message="Stopped all active recordings")

        except Exception as e:
            logger.error(f"Error stopping all recordings: {e}")
            return CommandResult(
                success=False, message=f"Error stopping all recordings: {str(e)}"
            )
