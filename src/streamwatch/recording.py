"""
Recording functionality for StreamWatch.
Handles stream recording using Streamlink.
"""

import logging
import os
import signal
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import config_parser

logger = logging.getLogger("streamwatch.recording")


class RecordingManager:
    """Manages stream recording operations."""

    def __init__(self):
        self.config = config_parser
        self.active_recordings: Dict[str, subprocess.Popen] = {}
        self.recording_threads: Dict[str, threading.Thread] = {}

    def get_output_directory(self) -> Path:
        """Get the configured output directory for recordings."""
        output_dir = self.config.get("Recording", "output_directory", fallback="")
        if not output_dir:
            # Default to ~/Videos/StreamWatch
            output_dir = str(Path.home() / "Videos" / "StreamWatch")

        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def generate_filename(self, stream_info: Dict[str, Any]) -> str:
        """Generate filename based on template and stream info."""
        template = self.config.get(
            "Recording",
            "filename_template",
            fallback="{platform}_{username}_{date}_{time}.{ext}",
        )

        now = datetime.now()
        format_ext = self.config.get("Recording", "default_format", fallback="mp4")

        # Sanitize values for filename
        platform = self._sanitize_filename(stream_info.get("platform", "unknown"))
        username = self._sanitize_filename(stream_info.get("username", "unknown"))

        filename = template.format(
            platform=platform,
            username=username,
            date=now.strftime("%Y%m%d"),
            time=now.strftime("%H%M%S"),
            ext=format_ext,
        )

        return filename

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use in filename."""
        # Remove/replace invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")
        return name.strip()

    def start_recording(self, url: str, stream_info: Dict[str, Any]) -> bool:
        """Start recording a stream."""
        if not self.config.getboolean("Recording", "enabled", fallback=True):
            logger.info("Recording is disabled in configuration")
            return False

        recording_id = f"{stream_info.get('platform', 'unknown')}_{stream_info.get('username', 'unknown')}"

        if recording_id in self.active_recordings:
            logger.warning(f"Recording already active for {recording_id}")
            return False

        try:
            output_dir = self.get_output_directory()
            filename = self.generate_filename(stream_info)
            output_path = output_dir / filename

            # Build streamlink command
            cmd = self._build_recording_command(url, str(output_path))

            logger.info(f"Starting recording: {recording_id} -> {output_path}")

            # Start recording in a separate thread
            thread = threading.Thread(
                target=self._record_stream,
                args=(recording_id, cmd, str(output_path)),
                daemon=True,
            )
            thread.start()

            self.recording_threads[recording_id] = thread
            return True

        except Exception as e:
            logger.error(f"Failed to start recording for {recording_id}: {e}")
            return False

    def _build_recording_command(self, url: str, output_path: str) -> list:
        """Build the streamlink command for recording."""
        quality = self.config.get("Recording", "quality", fallback="best")

        cmd = [
            "streamlink",
            "--output",
            output_path,
            "--force",  # Overwrite existing files
        ]

        # Add optional parameters
        max_size = self.config.getint("Recording", "max_file_size", fallback=0)
        if max_size > 0:
            cmd.extend(["--fs-safe-rules", "posix"])

        max_duration = self.config.getint("Recording", "max_duration", fallback=0)
        if max_duration > 0:
            cmd.extend(["--record-and-pipe", f"timeout {max_duration * 60}"])

        # Add Twitch ad blocking if enabled
        if self.config.getboolean("Streamlink", "twitch_disable_ads", fallback=True):
            cmd.extend(["--twitch-disable-ads"])

        cmd.extend([url, quality])
        return cmd

    def _record_stream(self, recording_id: str, cmd: list, output_path: str):
        """Execute the recording command."""
        try:
            logger.info(f"Executing recording command: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            self.active_recordings[recording_id] = process

            # Wait for process to complete
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                logger.info(f"Recording completed successfully: {output_path}")
            else:
                logger.error(f"Recording failed for {recording_id}: {stderr}")

        except Exception as e:
            logger.error(f"Recording error for {recording_id}: {e}")
        finally:
            # Clean up
            if recording_id in self.active_recordings:
                del self.active_recordings[recording_id]
            if recording_id in self.recording_threads:
                del self.recording_threads[recording_id]

    def stop_recording(self, recording_id: str) -> bool:
        """Stop an active recording."""
        if recording_id not in self.active_recordings:
            logger.warning(f"No active recording found for {recording_id}")
            return False

        try:
            process = self.active_recordings[recording_id]
            process.terminate()

            # Give it a moment to terminate gracefully
            process.wait(timeout=2)

            if process.poll() is None:
                # Force kill if still running
                process.kill()

            logger.info(f"Recording stopped: {recording_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop recording {recording_id}: {e}")
            return False

    def stop_all_recordings(self):
        """Stop all active recordings."""
        recording_ids = list(self.active_recordings.keys())
        for recording_id in recording_ids:
            self.stop_recording(recording_id)

    def get_active_recordings(self) -> Dict[str, bool]:
        """Get list of active recordings."""
        active = {}
        for recording_id, process in self.active_recordings.items():
            active[recording_id] = process.poll() is None
        return active

    def is_recording(self, stream_info: Dict[str, Any]) -> bool:
        """Check if a stream is currently being recorded."""
        recording_id = f"{stream_info.get('platform', 'unknown')}_{stream_info.get('username', 'unknown')}"
        return recording_id in self.active_recordings


# Global recording manager instance
recording_manager = RecordingManager()
