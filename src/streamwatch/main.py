import logging  # Import logging
import subprocess
import sys

from . import config  # To get USER_CONFIG_DIR
from . import ui  # For clear_screen
from .app import StreamWatchApp

# from pathlib import Path  # To construct log path


# --- Setup Logging ---
def setup_logging() -> None:
    """Sets up logging configuration for the application."""
    from .logging_config import setup_logging as setup_enhanced_logging

    # Use enhanced logging configuration
    setup_enhanced_logging(log_level="INFO", enable_console=True, enable_colors=True)

    logger = logging.getLogger(config.APP_NAME)
    logger.info("Enhanced logging system initialized")


def initial_streamlink_check() -> bool:
    """Checks if streamlink command is available and executable."""
    try:
        # Use --version as a lightweight check
        subprocess.run(
            ["streamlink", "--version"], capture_output=True, check=True, timeout=5
        )
        return True
    except FileNotFoundError:
        print("CRITICAL ERROR: streamlink command not found.", file=sys.stderr)
        print(
            "Please ensure streamlink is installed and in your system's PATH.",
            file=sys.stderr,
        )
        return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(
            f"CRITICAL ERROR: streamlink found but is not working correctly: {e}",
            file=sys.stderr,
        )
        return False
    except Exception as e:  # Catch any other unexpected errors
        print(
            f"CRITICAL ERROR: An unexpected issue occurred while checking for streamlink: {e}",
            file=sys.stderr,
        )
        return False


def app() -> None:
    """Main entry point for the StreamWatch CLI application (for script entry point)."""
    main()


def main() -> None:
    setup_logging()
    logger = logging.getLogger(config.APP_NAME)
    logger.info("StreamWatch application started.")

    if not initial_streamlink_check():
        logger.critical("Streamlink check failed. Application cannot continue.")
        # ui.console.print(...) already handles user message
        sys.exit(1)

    try:
        # Create and run the StreamWatch application with dependency injection
        app = StreamWatchApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user (KeyboardInterrupt).")
        ui.clear_screen()
        ui.console.print(
            "\nScript interrupted by user. Exiting gracefully. Goodbye!", style="info"
        )


if __name__ == "__main__":
    # This allows running the script directly like: python -m stream_manager_cli.main
    # However, the primary execution method after packaging will be via the entry point.
    main()
