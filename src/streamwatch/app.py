"""
StreamWatch Application Class

This module contains the main application class that orchestrates all components
using dependency injection, providing a clean separation of concerns and
improved testability.
"""

import logging
from typing import Any, Dict, List, Optional

from . import config, stream_checker, ui
from .container import DIContainer, ServiceRegistry

logger = logging.getLogger(config.APP_NAME + ".app")


class StreamWatchApp:
    """
    Main application class for StreamWatch.

    This class orchestrates all application components using dependency injection,
    managing the application lifecycle and coordinating between different services.
    """

    def __init__(self, container: Optional[DIContainer] = None):
        """
        Initialize the StreamWatch application.

        Args:
            container: Optional DI container. If None, a new one will be created and configured.
        """
        self.container = container or self._create_container()
        self.logger = logging.getLogger(f"{config.APP_NAME}.app")

        # Get services from container
        self.menu_handler = self.container.get("menu_handler")
        self.stream_manager = self.container.get("stream_manager")
        self.playback_controller = self.container.get("playback_controller")

        self.logger.info(
            "StreamWatch application initialized with dependency injection"
        )

    def _create_container(self) -> DIContainer:
        """
        Create and configure a new DI container.

        Returns:
            Configured DI container
        """
        container = DIContainer()
        ServiceRegistry.configure_container(container)
        return container

    def run(self) -> None:
        """
        Run the main application loop.

        This is the main entry point that starts the interactive loop
        and handles the application lifecycle.
        """
        self.logger.info("Starting StreamWatch application")

        try:
            self._run_interactive_loop()
        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user (KeyboardInterrupt)")
            self._handle_graceful_shutdown(
                "Script interrupted by user. Exiting gracefully. Goodbye!"
            )
        except Exception as e:
            self.logger.critical(
                "An unexpected critical error occurred in the application",
                exc_info=True,
            )
            self._handle_error_shutdown(e)

        self.logger.info("StreamWatch application finished")

    def _run_interactive_loop(self) -> None:
        """Main interactive loop for the StreamWatch application."""
        self.logger.info("Starting interactive loop")

        # --- First-Time User Experience Check ---
        if not config.is_first_run_completed():
            self._show_first_time_welcome()
            config.mark_first_run_completed()
            self.logger.info("First run experience completed and marked")
            needs_refresh = True
        else:
            needs_refresh = True  # Default to refresh on normal startup

        live_streams: List[Dict[str, Any]] = []

        while True:
            if needs_refresh:
                live_streams = self._refresh_live_streams()
                needs_refresh = False
                self.menu_handler.clear_message()

            # Display current status and menu
            if not needs_refresh:  # Avoid double clear if refresh just happened
                ui.clear_screen()
                ui.console.print("--- StreamWatch ---", style="title")

            if not live_streams:
                ui.console.print("No favorite streams currently live.", style="dimmed")
            else:
                # Use pagination-aware display method
                self.menu_handler.display_streams_with_pagination(
                    live_streams, title="--- Live Streams ---"
                )

            self.menu_handler.display_main_menu(len(live_streams))
            choice = self.menu_handler.handle_user_input()

            # Process choice using MenuHandler
            needs_refresh, should_continue = self.menu_handler.process_menu_choice(
                choice, live_streams, self.stream_manager, self.playback_controller
            )

            if not should_continue:
                break

        self.logger.info("Interactive loop completed")

    def _refresh_live_streams(self) -> List[Dict[str, Any]]:
        """
        Refresh the list of live streams.

        Returns:
            List of currently live streams
        """
        self.logger.info("Refreshing live streams")
        ui.clear_screen()
        ui.console.print("--- StreamWatch ---", style="title")
        ui.console.print("Checking stream status...", style="info")

        try:
            all_configured_streams = self.stream_manager.load_streams()
            if not all_configured_streams:
                ui.console.print(
                    "No streams configured. Use 'A' to add some!", style="warning"
                )
                return []

            # Use async concurrent processing for better performance
            live_streams = stream_checker.fetch_live_streams(
                all_configured_streams, use_async=True
            )

            if live_streams:
                self.logger.info(f"Found {len(live_streams)} live streams")
            else:
                self.logger.info("No live streams found")
                ui.console.print("No streams are currently live.", style="dimmed")

            return live_streams

        except Exception as e:
            error_msg = f"Error refreshing streams: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            ui.console.print(f"Error refreshing streams: {str(e)}", style="error")
            return []

    def _show_first_time_welcome(self) -> None:
        """Display first-time user welcome message."""
        ui.clear_screen()
        ui.console.print("--- Welcome to StreamWatch! ---", style="title")
        ui.console.print(
            "This appears to be your first time running StreamWatch.", style="info"
        )
        ui.console.print(
            "To get started, you'll want to add some stream URLs using the 'A' option in the main menu.",
            style="info",
        )
        ui.console.print(
            "StreamWatch supports Twitch, YouTube, and many other platforms via streamlink.",
            style="info",
        )
        ui.console.print("Press Enter to continue to the main menu...", style="dimmed")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass

    def _handle_graceful_shutdown(self, message: str) -> None:
        """
        Handle graceful application shutdown.

        Args:
            message: Message to display to the user
        """
        ui.clear_screen()
        ui.console.print(f"\n{message}", style="info")

    def _handle_error_shutdown(self, error: Exception) -> None:
        """
        Handle error-based application shutdown.

        Args:
            error: The exception that caused the shutdown
        """
        ui.clear_screen()
        ui.console.print(
            f"\n[error]An unexpected critical error occurred: {error}[/error]",
            style="error",
        )
        ui.console.print("Please check the log file for more details.", style="dimmed")
        ui.console.print(
            f"Log file location: {config.USER_CONFIG_DIR / 'logs' / 'streamwatch.log'}",
            style="dimmed",
        )

    def get_container(self) -> DIContainer:
        """
        Get the dependency injection container.

        Returns:
            The DI container used by this application instance
        """
        return self.container

    def get_service(self, service_name: str) -> Any:
        """
        Get a service from the DI container.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            The requested service instance
        """
        return self.container.get(service_name)

    def shutdown(self) -> None:
        """
        Shutdown the application and clean up resources.

        This method can be called to gracefully shutdown the application
        and perform any necessary cleanup.
        """
        self.logger.info("Shutting down StreamWatch application")
        # Add any cleanup logic here if needed in the future
        self.logger.info("StreamWatch application shutdown completed")


__all__ = [
    "StreamWatchApp",
]
