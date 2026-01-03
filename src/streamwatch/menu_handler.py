"""Menu handling functionality for StreamWatch application."""

import logging
import sys
from typing import Any, Dict, List, Optional

from . import config, ui
from .commands import (
    AddStreamCommand,
    CommandInvoker,
    ExportStreamsCommand,
    ImportStreamsCommand,
    ListStreamsCommand,
    PlayLastStreamCommand,
    PlayStreamByIndexCommand,
    PlayStreamCommand,
    RefreshStreamsCommand,
    RemoveStreamCommand,
)

# Import pagination utilities
try:
    from .ui.display import display_filter_summary, display_paginated_stream_list
    from .ui.input_handler import handle_pagination_command
    from .ui.pagination import get_stream_list_manager

    PAGINATION_AVAILABLE = True
except ImportError:
    PAGINATION_AVAILABLE = False

logger = logging.getLogger(config.APP_NAME + ".menu_handler")


class MenuHandler:
    """Handles menu display and user input processing for the StreamWatch application."""

    def __init__(self, command_invoker: Optional[CommandInvoker] = None):
        """
        Initialize the MenuHandler.

        Args:
            command_invoker: CommandInvoker instance for executing commands.
                           If None, a new instance will be created.
        """
        self.last_message = ""
        self.command_invoker = command_invoker or CommandInvoker()
        self.use_pagination = (
            PAGINATION_AVAILABLE and config.get_lazy_load_threshold() > 0
        )

    def display_main_menu(self, live_streams_count: int) -> None:
        """Display the main menu with current status."""
        if self.last_message:
            # Style based on message content
            msg_style = "info"
            if (
                "error" in self.last_message.lower()
                or "fail" in self.last_message.lower()
            ):
                msg_style = "error"
            elif "success" in self.last_message.lower():
                msg_style = "success"
            elif "warn" in self.last_message.lower():
                msg_style = "warning"
            ui.console.print(f"\n{self.last_message}\n", style=msg_style)
            self.last_message = ""

        if not live_streams_count:
            ui.console.print("No favorite streams currently live.", style="dimmed")

        ui.display_main_menu(live_streams_count)

    def handle_user_input(self) -> str:
        """Get user input for main menu actions."""
        return ui.prompt_main_menu_action()

    def process_menu_choice(
        self,
        choice: str,
        live_streams: List[Dict[str, Any]],
        stream_manager: Any,  # Will be StreamManager instance
        playback_controller: Any,  # Will be PlaybackController instance
    ) -> tuple[bool, bool]:
        """
        Process the user's menu choice.

        Args:
            choice: The user's menu choice
            live_streams: List of currently live streams
            stream_manager: StreamManager instance for stream operations
            playback_controller: PlaybackController instance for playback operations

        Returns:
            Tuple of (needs_refresh, should_continue)
        """
        needs_refresh = False
        should_continue = True

        # If user just presses Enter and live streams exist, trigger selection
        if not choice and live_streams:
            # Create and execute PlayStreamCommand
            play_command = PlayStreamCommand(live_streams, playback_controller)
            result = self.command_invoker.execute_command(play_command)

            self.last_message = result.message
            needs_refresh = result.needs_refresh
            should_continue = result.should_continue

            # Handle application quit
            if not result.should_continue:
                sys.exit(0)

        elif choice.isdigit():  # If they still type a number at main menu
            try:
                stream_idx = int(choice) - 1
                # Create and execute PlayStreamByIndexCommand
                play_by_index_command = PlayStreamByIndexCommand(
                    stream_idx, live_streams, playback_controller
                )
                result = self.command_invoker.execute_command(play_by_index_command)

                self.last_message = result.message
                needs_refresh = result.needs_refresh
                should_continue = result.should_continue

                # Handle application quit
                if not result.should_continue:
                    sys.exit(0)

            except ValueError:
                logger.warning("Invalid input for stream selection.")
                self.last_message = "Invalid input."

        elif choice == "l":
            # Create and execute ListStreamsCommand
            list_command = ListStreamsCommand(stream_manager)
            result = self.command_invoker.execute_command(list_command)
            self.last_message = result.message

        elif choice == "a":
            # Create and execute AddStreamCommand
            add_command = AddStreamCommand(stream_manager)
            result = self.command_invoker.execute_command(add_command)
            self.last_message = result.message
            needs_refresh = result.needs_refresh

        elif choice == "r":
            # Create and execute RemoveStreamCommand
            remove_command = RemoveStreamCommand(stream_manager)
            result = self.command_invoker.execute_command(remove_command)
            self.last_message = result.message
            needs_refresh = result.needs_refresh

        elif choice == "i":  # IMPORT
            # Create and execute ImportStreamsCommand
            import_command = ImportStreamsCommand(stream_manager)
            result = self.command_invoker.execute_command(import_command)
            self.last_message = result.message
            needs_refresh = result.needs_refresh

        elif choice == "e":  # EXPORT
            # Create and execute ExportStreamsCommand
            export_command = ExportStreamsCommand(stream_manager)
            result = self.command_invoker.execute_command(export_command)
            self.last_message = result.message

        elif choice == "t":  # MANAGE TAGS
            # Handle tag management
            stream_manager.manage_tags()

        elif choice == "h":  # EXPORT HISTORY & ANALYTICS
            # Show export history
            stream_manager.show_export_history()

        elif choice == "v":  # RECORDING CONTROLS
            from .recording_menu import RecordingMenuHandler

            recording_menu = RecordingMenuHandler(ui.console)
            recording_menu.show_recording_menu(live_streams)

        elif choice == "f":
            # Create and execute RefreshStreamsCommand
            refresh_command = RefreshStreamsCommand(stream_manager)
            result = self.command_invoker.execute_command(refresh_command)
            needs_refresh = result.needs_refresh

        elif choice == "q":
            logger.info("User quit application from main menu.")
            ui.clear_screen()
            ui.console.print("Exiting StreamWatch. Goodbye!", style="success")
            should_continue = False

        elif choice == "p" and config.get_last_played_url():  # Play Last
            # Create and execute PlayLastStreamCommand
            play_last_command = PlayLastStreamCommand(live_streams, playback_controller)
            result = self.command_invoker.execute_command(play_last_command)
            self.last_message = result.message
            needs_refresh = result.needs_refresh
            should_continue = result.should_continue

            # Handle application quit
            if not result.should_continue:
                sys.exit(0)

        else:
            # Check if it's a pagination command
            if PAGINATION_AVAILABLE:
                # Get all streams for pagination context
                all_streams = (
                    stream_manager.load_streams()
                    if hasattr(stream_manager, "load_streams")
                    else live_streams
                )

                if handle_pagination_command(choice, all_streams):
                    # Pagination command was handled, no refresh needed
                    # The pagination system manages its own display
                    pass
                else:
                    # Unknown command
                    logger.warning(f"Unknown command: {choice}")
                    self.last_message = (
                        f"Unknown command: '{choice}'. Type 'h' for help."
                    )
            else:
                # Unknown command without pagination
                logger.warning(f"Unknown command: {choice}")
                self.last_message = f"Unknown command: '{choice}'. Type 'h' for help."

        return needs_refresh, should_continue

    def display_streams_with_pagination(
        self, streams: List[Dict[str, Any]], title: str = "--- Live Streams ---"
    ) -> None:
        """
        Display streams with pagination support if enabled and threshold is met.

        Args:
            streams: List of streams to display
            title: Title to display above the streams
        """
        if not streams:
            ui.console.print("No streams to display.", style="dimmed")
            return

        # Check if pagination should be used
        should_paginate = (
            PAGINATION_AVAILABLE
            and self.use_pagination
            and len(streams) >= config.get_lazy_load_threshold()
        )

        if should_paginate:
            # Use pagination
            manager = get_stream_list_manager()
            page_streams, pagination_info = manager.get_page(streams)

            # --- Lazy Loading Enrichment Step ---
            from .core.models import StreamInfo
            from .ui.pagination import get_lazy_loader

            lazy_loader = get_lazy_loader()
            enriched_page_streams = []

            # Convert dicts back to StreamInfo models for processing
            thin_stream_models = [StreamInfo.model_validate(s) for s in page_streams]

            for stream_model in thin_stream_models:
                # Get enriched details from the lazy loader (uses cache)
                enriched_model = lazy_loader.get_details(stream_model)
                enriched_page_streams.append(enriched_model.model_dump())
            # --- End of Lazy Loading Step ---

            # Display filter summary if filters are active
            filter_summary = manager.get_filter_summary()
            if filter_summary:
                display_filter_summary(filter_summary)

            # Display paginated streams (now enriched)
            display_paginated_stream_list(
                enriched_page_streams,
                pagination_info,
                title=title,
                show_pagination_controls=True,
                clear_screen_first=False,
            )
        else:
            # Use regular display
            ui.display_stream_list(streams, title)

    def set_message(self, message: str) -> None:
        """Set a message to be displayed on the next menu display."""
        self.last_message = message

    def clear_message(self) -> None:
        """Clear the current message."""
        self.last_message = ""

    def undo_last_command(self) -> bool:
        """
        Undo the last command if possible.

        Returns:
            bool: True if undo was successful, False otherwise
        """
        if self.command_invoker.can_undo():
            result = self.command_invoker.undo_last_command()
            self.last_message = result.message
            return result.success
        else:
            self.last_message = "No commands available to undo."
            return False

    def get_command_history(self) -> List[str]:
        """
        Get a list of executed command names.

        Returns:
            List[str]: List of command names in chronological order
        """
        return [cmd.name for cmd in self.command_invoker.get_command_history()]

    def get_command_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about command execution.

        Returns:
            Dict[str, Any]: Command execution statistics
        """
        return self.command_invoker.get_statistics()
