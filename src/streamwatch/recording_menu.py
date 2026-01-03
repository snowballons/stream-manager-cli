"""Recording menu handler for StreamWatch."""

import logging
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .recording import recording_manager

logger = logging.getLogger("streamwatch.recording_menu")


class RecordingMenuHandler:
    """Handles the recording controls submenu."""

    def __init__(self, console: Console):
        self.console = console

    def show_recording_menu(self, live_streams: List[Dict[str, Any]]) -> bool:
        """
        Show recording controls menu.

        Args:
            live_streams: List of currently live streams

        Returns:
            bool: True if should return to main menu, False to continue
        """
        while True:
            self._display_recording_menu()

            choice = input("Enter recording choice: ").strip().lower()

            if choice in ["q", "quit", "back", ""]:
                return True

            elif choice == "1":
                self._start_recording_menu(live_streams)

            elif choice == "2":
                self._list_active_recordings()

            elif choice == "3":
                self._stop_recording_menu()

            elif choice == "4":
                self._stop_all_recordings()

            elif choice == "5":
                self._recording_settings_menu()

            elif choice == "6":
                self._open_recordings_folder()

            else:
                self.console.print("[red]Invalid choice. Please try again.[/red]")

    def _display_recording_menu(self):
        """Display the recording controls menu."""
        self.console.clear()

        # Header
        text = Text()
        text.append("--- Recording Controls ---\n\n", style="bold cyan")

        # Menu options
        text.append("  [", style="dimmed")
        text.append("1", style="bold green")
        text.append("]  Start recording selected stream\n", style="white")

        text.append("  [", style="dimmed")
        text.append("2", style="bold green")
        text.append("]  List active recordings\n", style="white")

        text.append("  [", style="dimmed")
        text.append("3", style="bold green")
        text.append("]  Stop recording\n", style="white")

        text.append("  [", style="dimmed")
        text.append("4", style="bold green")
        text.append("]  Stop all recordings\n", style="white")

        text.append("  [", style="dimmed")
        text.append("5", style="bold green")
        text.append("]  Recording settings\n", style="white")

        text.append("  [", style="dimmed")
        text.append("6", style="bold green")
        text.append("]  View recordings folder\n", style="white")

        text.append("\n  [", style="dimmed")
        text.append("Q", style="bold red")
        text.append("]  Back to main menu\n\n", style="white")

        self.console.print(text)

        # Show active recordings count
        active_recordings = recording_manager.get_active_recordings()
        if active_recordings:
            self.console.print(
                f"[yellow]Active recordings: {len(active_recordings)}[/yellow]\n"
            )

    def _start_recording_menu(self, live_streams: List[Dict[str, Any]]):
        """Show menu to start recording a stream."""
        if not live_streams:
            self.console.print("[red]No live streams available to record.[/red]")
            input("Press Enter to continue...")
            return

        self.console.print("\n[bold]Select stream to record:[/bold]")

        # Display live streams
        for i, stream in enumerate(live_streams, 1):
            username = stream.get("username", "Unknown")
            platform = stream.get("platform", "Unknown")
            category = stream.get("category", "Unknown")

            # Check if already recording
            is_recording = recording_manager.is_recording(stream)
            status = (
                "[red]●[/red] Recording"
                if is_recording
                else "[green]○[/green] Available"
            )

            self.console.print(f"  [{i}] {status} {username} ({platform}) - {category}")

        choice = input("\nEnter stream number (or Q to cancel): ").strip().lower()

        if choice in ["q", "quit", "cancel", ""]:
            return

        try:
            stream_index = int(choice) - 1
            if 0 <= stream_index < len(live_streams):
                stream = live_streams[stream_index]

                # Check if already recording
                if recording_manager.is_recording(stream):
                    self.console.print(
                        "[yellow]This stream is already being recorded.[/yellow]"
                    )
                    input("Press Enter to continue...")
                    return

                # Start recording
                url = stream.get("url", "")
                if recording_manager.start_recording(url, stream):
                    username = stream.get("username", "Unknown")
                    platform = stream.get("platform", "Unknown")
                    self.console.print(
                        f"[green]Started recording: {username} ({platform})[/green]"
                    )
                else:
                    self.console.print("[red]Failed to start recording.[/red]")

                input("Press Enter to continue...")

        except (ValueError, IndexError):
            self.console.print("[red]Invalid selection.[/red]")
            input("Press Enter to continue...")

    def _list_active_recordings(self):
        """List all active recordings."""
        active_recordings = recording_manager.get_active_recordings()

        if not active_recordings:
            self.console.print("[yellow]No active recordings.[/yellow]")
            input("Press Enter to continue...")
            return

        self.console.print("\n[bold]Active Recordings:[/bold]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan")
        table.add_column("Stream", style="green")
        table.add_column("Status", style="yellow")

        for recording_id, is_active in active_recordings.items():
            status = "Recording" if is_active else "Stopped"
            # Parse recording_id (format: platform_username)
            parts = recording_id.split("_", 1)
            if len(parts) == 2:
                platform, username = parts
                stream_name = f"{username} ({platform})"
            else:
                stream_name = recording_id

            table.add_row(recording_id, stream_name, status)

        self.console.print(table)
        input("\nPress Enter to continue...")

    def _stop_recording_menu(self):
        """Show menu to stop a specific recording."""
        active_recordings = recording_manager.get_active_recordings()

        if not active_recordings:
            self.console.print("[yellow]No active recordings to stop.[/yellow]")
            input("Press Enter to continue...")
            return

        self.console.print("\n[bold]Select recording to stop:[/bold]")

        recording_list = list(active_recordings.keys())
        for i, recording_id in enumerate(recording_list, 1):
            # Parse recording_id for display
            parts = recording_id.split("_", 1)
            if len(parts) == 2:
                platform, username = parts
                display_name = f"{username} ({platform})"
            else:
                display_name = recording_id

            self.console.print(f"  [{i}] {display_name}")

        choice = input("\nEnter recording number (or Q to cancel): ").strip().lower()

        if choice in ["q", "quit", "cancel", ""]:
            return

        try:
            recording_index = int(choice) - 1
            if 0 <= recording_index < len(recording_list):
                recording_id = recording_list[recording_index]

                if recording_manager.stop_recording(recording_id):
                    self.console.print(
                        f"[green]Stopped recording: {recording_id}[/green]"
                    )
                else:
                    self.console.print(
                        f"[red]Failed to stop recording: {recording_id}[/red]"
                    )

                input("Press Enter to continue...")

        except (ValueError, IndexError):
            self.console.print("[red]Invalid selection.[/red]")
            input("Press Enter to continue...")

    def _stop_all_recordings(self):
        """Stop all active recordings."""
        active_recordings = recording_manager.get_active_recordings()

        if not active_recordings:
            self.console.print("[yellow]No active recordings to stop.[/yellow]")
            input("Press Enter to continue...")
            return

        confirm = (
            input(f"Stop all {len(active_recordings)} recordings? (y/N): ")
            .strip()
            .lower()
        )

        if confirm in ["y", "yes"]:
            recording_manager.stop_all_recordings()
            self.console.print("[green]All recordings stopped.[/green]")
        else:
            self.console.print("[yellow]Cancelled.[/yellow]")

        input("Press Enter to continue...")

    def _recording_settings_menu(self):
        """Show recording settings menu."""
        self.console.print("[yellow]Recording settings - Feature coming soon![/yellow]")
        input("Press Enter to continue...")

    def _open_recordings_folder(self):
        """Open the recordings folder."""
        import platform
        import subprocess

        try:
            recordings_dir = recording_manager.get_output_directory()

            # Open folder based on OS
            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", str(recordings_dir)])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(recordings_dir)])
            else:  # Linux
                subprocess.run(["xdg-open", str(recordings_dir)])

            self.console.print(
                f"[green]Opened recordings folder: {recordings_dir}[/green]"
            )

        except Exception as e:
            self.console.print(f"[red]Failed to open folder: {e}[/red]")
            self.console.print(
                f"[yellow]Recordings are saved to: {recording_manager.get_output_directory()}[/yellow]"
            )

        input("Press Enter to continue...")
