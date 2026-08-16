"""
StreamWatch UI Input Handler Module

This module contains all input handling and user interaction functions for the StreamWatch CLI application.
It handles prompts, dialogs, and user input processing.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import message_dialog, radiolist_dialog
from rich.text import Text

from .. import config
from .display import clear_screen, format_stream_for_display
from .styles import console, dialog_style, playback_menu_style

# Import security utilities
try:
    from .security import (
        UISecurityError,
        log_user_action,
        safe_format_error_message,
        sanitize_user_input,
        validate_ui_command,
    )
    from ..validation.validators import SecurityError

    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

# Import pagination utilities
try:
    from .display import (
        display_category_filter_prompt,
        display_pagination_help,
        display_platform_filter_prompt,
        display_search_prompt,
    )
    from .pagination import get_stream_list_manager

    PAGINATION_AVAILABLE = True
except ImportError:
    PAGINATION_AVAILABLE = False

# Get a logger for this module
logger = logging.getLogger(config.APP_NAME + ".ui.input_handler")


def prompt_for_filepath(
    prompt_text: str = "Enter file path: ", default_filename: str = ""
) -> Optional[str]:
    """Prompts the user for a file path and validates it."""
    console.print(
        "Enter the path for the file. You can use `~` for your home directory."
    )
    console.print("Press Ctrl+D or Ctrl+C to cancel.", style="dimmed")
    try:
        raw_path = prompt(prompt_text, default=default_filename, style=dialog_style)
        if not raw_path:
            return None

        # Try validation if available, but don't fail if validator has issues
        try:
            from ..validation.validators import ValidationError, validate_file_path

            validated_path = validate_file_path(raw_path)
            return str(validated_path)
        except ImportError:
            # Fallback: basic path validation without validators module
            from pathlib import Path

            try:
                path = Path(raw_path).expanduser()
                return str(path)
            except Exception as e:
                logger.debug(f"Basic path validation failed: {e}")
                return raw_path  # Return raw path as last resort
        except (ValidationError, SecurityError) as e:
            # Log the validation error but allow the operation to continue with basic validation
            logger.warning(f"Path validation warning: {e}")
            try:
                from pathlib import Path

                path = Path(raw_path).expanduser()
                return str(path)
            except Exception:
                return raw_path  # Return raw path if all validation fails

    except (EOFError, KeyboardInterrupt):
        console.print("\nOperation cancelled.", style="warning")
        return None


def select_stream_dialog(
    stream_info_list: List[Dict[str, Any]],
    title: str = "Select a stream to play",
    prompt_text: str = "Choose a stream:",
) -> Optional[Dict[str, Any]]:
    """Displays an interactive dialog to select a stream."""
    if not stream_info_list:
        message_dialog(
            title="No Streams",
            text="There are no streams available to select.",
            style=dialog_style,
        ).run()
        return None

    choices = []
    for i, s_info in enumerate(stream_info_list):
        display_text_str = str(
            format_stream_for_display(s_info, index=i, for_prompt_toolkit=True)
        )
        choices.append((s_info, display_text_str))

    rich_prompt_text = Text()
    rich_prompt_text.append(prompt_text + "\n")
    rich_prompt_text.append("(Use ", style="dimmed")
    rich_prompt_text.append("↑↓ arrows", style="bold cyan")
    rich_prompt_text.append(", ", style="dimmed")
    rich_prompt_text.append("number", style="bold cyan")
    rich_prompt_text.append(", or ", style="dimmed")
    rich_prompt_text.append("first letter", style="bold cyan")
    rich_prompt_text.append(". ", style="dimmed")
    rich_prompt_text.append("Enter", style="bold green")
    rich_prompt_text.append(" to select, ", style="dimmed")
    rich_prompt_text.append("Esc/Ctrl+C", style="bold red")
    rich_prompt_text.append(" to cancel)", style="dimmed")

    selected_stream_info = radiolist_dialog(
        title=title, text=str(rich_prompt_text), values=choices, style=dialog_style
    ).run()
    return selected_stream_info


def prompt_add_streams() -> List[Dict[str, str]]:
    """Prompts the user for URLs and optional aliases, returning raw input."""
    clear_screen()
    console.print("--- Add New Stream(s) ---", style="title")
    console.print(
        "Enter stream URL(s). You can provide an optional alias after the URL with a space."
    )
    console.print("Example: [cyan]https://twitch.tv/shroud My Favorite FPS[/cyan]")
    console.print(
        "Example (multiple): [cyan]https://youtube.com/@LTT, https://twitch.tv/pokimane Queen Poki[/cyan]"
    )
    console.print("Press Ctrl+D or Ctrl+C to cancel.", style="dimmed")
    try:
        urls_input = prompt("URL(s) [and optional alias(es)]: ", style=dialog_style)
        if not urls_input:
            return []

        new_streams_data = []
        entries = urls_input.split(",")
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            parts = entry.split(maxsplit=1)
            url = parts[0].strip()
            alias = parts[1].strip() if len(parts) > 1 else ""

            new_streams_data.append({"url": url, "alias": alias})

        return new_streams_data
    except (EOFError, KeyboardInterrupt):
        console.print("\nAdd operation cancelled.", style="warning")
        return []


def prompt_remove_streams_dialog(
    all_streams_data: List[Dict[str, Any]], title: str = "Select streams to REMOVE"
) -> Optional[List[int]]:
    """Now displays alias and URL for easier identification."""
    if not all_streams_data:
        message_dialog(
            title="No Streams",
            text="There are no configured streams to remove.",
            style=dialog_style,
        ).run()
        return None

    clear_screen()
    console.print("--- Remove Configured Stream(s) ---", style="title")
    for i, s_data in enumerate(all_streams_data):
        console.print(
            f"  [{i+1}] [highlight]{s_data.get('alias', s_data.get('url'))}[/highlight] [dim]({s_data.get('url')})[/dim]"
        )

    console.print("\nEnter the number(s) of the stream(s) you want to remove.")
    console.print(
        "Multiple numbers separated by spaces or commas (e.g., 1 3 4 or 1,3,4).",
        style="dimmed",
    )
    console.print(
        "Press Ctrl+D or Ctrl+C (or Esc then Enter on Windows) to cancel.",
        style="dimmed",
    )

    try:
        choice_input = prompt("Remove number(s): ", style=dialog_style)
        if not choice_input:
            return []
    except (EOFError, KeyboardInterrupt):
        console.print("\nRemove operation cancelled.", style="warning")
        return []

    try:
        raw_indices_str = choice_input.replace(",", " ").split()
        indices_to_remove = []
        invalid_inputs = []
        for s_idx_str in raw_indices_str:
            s_idx_str = s_idx_str.strip()
            if s_idx_str.isdigit():
                idx_val = int(s_idx_str) - 1
                if 0 <= idx_val < len(all_streams_data):
                    indices_to_remove.append(idx_val)
                else:
                    invalid_inputs.append(s_idx_str)
            elif s_idx_str:
                invalid_inputs.append(s_idx_str)

        if invalid_inputs:
            console.print(
                f"Warning: Ignored invalid input(s): {', '.join(invalid_inputs)}",
                style="warning",
            )

        return sorted(list(set(indices_to_remove)), reverse=True)
    except ValueError:
        console.print("Invalid input format. Please enter numbers.", style="error")
        return []


def prompt_main_menu_action() -> str:
    """Gets user input for main menu actions with validation."""
    try:
        choice = (
            input("Enter choice (or press Enter to select stream if live): ")
            .strip()
            .lower()
        )

        # Security: Validate command input
        if SECURITY_AVAILABLE and choice:
            try:
                # Define allowed main menu commands
                allowed_commands = [
                    "a",
                    "add",
                    "r",
                    "remove",
                    "e",
                    "export",
                    "i",
                    "import",
                    "v",
                    "recording",
                    "c",
                    "check",
                    "s",
                    "settings",
                    "h",
                    "help",
                    "q",
                    "quit",
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "7",
                    "8",
                    "9",
                    "0",  # Stream selection numbers
                    # Pagination commands
                    "n",
                    "next",
                    "p",
                    "prev",
                    "f",
                    "first",
                    "l",
                    "last",
                    "search",
                    "cf",
                    "pf",
                    "clear",
                ]

                # Allow empty choice (default action)
                if choice == "":
                    return choice

                # Check if it's a number (stream selection)
                if choice.isdigit():
                    return choice

                # Validate against allowed commands
                validated_choice = validate_ui_command(choice, allowed_commands)
                log_user_action("main_menu_action", {"command": validated_choice})

                return validated_choice

            except UISecurityError as e:
                console.print(
                    f"[red]Invalid command:[/red] {safe_format_error_message(e)}"
                )
                return ""  # Return empty to show menu again

        return choice

    except (EOFError, KeyboardInterrupt):
        return "q"


def prompt_search_term() -> Optional[str]:
    """
    Prompt user for search term with validation.

    Returns:
        Search term or None if cancelled
    """
    if not PAGINATION_AVAILABLE:
        return None

    try:
        display_search_prompt()
        search_term = prompt("Search term: ", style=dialog_style)

        if search_term is None:
            return None

        search_term = search_term.strip()

        # Security: Validate search input
        if SECURITY_AVAILABLE and search_term:
            try:
                search_term = sanitize_user_input(
                    search_term, "search_term", max_length=100
                )
                log_user_action("search_streams", {"term_length": len(search_term)})
            except UISecurityError as e:
                console.print(
                    f"[red]Invalid search term:[/red] {safe_format_error_message(e)}"
                )
                return None

        return search_term if search_term else ""

    except (EOFError, KeyboardInterrupt):
        console.print("\nSearch cancelled.", style="warning")
        return None


def prompt_category_filter(available_categories: List[str]) -> Optional[str]:
    """
    Prompt user for category filter with validation.

    Args:
        available_categories: List of available categories

    Returns:
        Category filter or None if cancelled
    """
    if not PAGINATION_AVAILABLE:
        return None

    try:
        display_category_filter_prompt(available_categories)
        category = prompt("Category filter: ", style=dialog_style)

        if category is None:
            return None

        category = category.strip()

        # Security: Validate category input
        if SECURITY_AVAILABLE and category:
            try:
                category = sanitize_user_input(
                    category, "category_filter", max_length=100
                )
                log_user_action("filter_by_category", {"category": category})
            except UISecurityError as e:
                console.print(
                    f"[red]Invalid category:[/red] {safe_format_error_message(e)}"
                )
                return None

        return category if category else ""

    except (EOFError, KeyboardInterrupt):
        console.print("\nCategory filter cancelled.", style="warning")
        return None


def prompt_platform_filter(available_platforms: List[str]) -> Optional[str]:
    """
    Prompt user for platform filter with validation.

    Args:
        available_platforms: List of available platforms

    Returns:
        Platform filter or None if cancelled
    """
    if not PAGINATION_AVAILABLE:
        return None

    try:
        display_platform_filter_prompt(available_platforms)
        platform = prompt("Platform filter: ", style=dialog_style)

        if platform is None:
            return None

        platform = platform.strip()

        # Security: Validate platform input
        if SECURITY_AVAILABLE and platform:
            try:
                platform = sanitize_user_input(
                    platform, "platform_filter", max_length=50
                )
                log_user_action("filter_by_platform", {"platform": platform})
            except UISecurityError as e:
                console.print(
                    f"[red]Invalid platform:[/red] {safe_format_error_message(e)}"
                )
                return None

        return platform if platform else ""

    except (EOFError, KeyboardInterrupt):
        console.print("\nPlatform filter cancelled.", style="warning")
        return None


def handle_pagination_command(command: str, streams: List[Dict[str, Any]]) -> bool:
    """
    Handle pagination-specific commands.

    Args:
        command: The pagination command to handle
        streams: List of all streams for context

    Returns:
        True if command was handled, False otherwise
    """
    if not PAGINATION_AVAILABLE:
        return False

    manager = get_stream_list_manager()

    if command in ["n", "next"]:
        manager.next_page(streams)
        return True

    elif command in ["p", "prev"]:
        manager.previous_page(streams)
        return True

    elif command in ["f", "first"]:
        manager.first_page(streams)
        return True

    elif command in ["l", "last"]:
        manager.last_page(streams)
        return True

    elif command in ["s", "search"]:
        search_term = prompt_search_term()
        if search_term is not None:
            manager.set_search_filter(search_term)
            if search_term:
                console.print(f"Search filter set to: '{search_term}'", style="info")
            else:
                console.print("Search filter cleared", style="info")
        return True

    elif command == "cf":
        available_categories = manager.get_available_categories(streams)
        category = prompt_category_filter(available_categories)
        if category is not None:
            manager.set_category_filter(category)
            if category:
                console.print(f"Category filter set to: '{category}'", style="info")
            else:
                console.print("Category filter cleared", style="info")
        return True

    elif command == "pf":
        available_platforms = manager.get_available_platforms(streams)
        platform = prompt_platform_filter(available_platforms)
        if platform is not None:
            manager.set_platform_filter(platform)
            if platform:
                console.print(f"Platform filter set to: '{platform}'", style="info")
            else:
                console.print("Platform filter cleared", style="info")
        return True

    elif command == "clear":
        manager.clear_filters()
        console.print("All filters cleared", style="info")
        return True

    elif command in ["h", "help"]:
        display_pagination_help()
        input("Press Enter to continue...")
        return True

    return False


def show_playback_menu(
    stream_url: str, current_quality: str, has_next: bool, has_previous: bool
) -> Tuple[str, Optional[str]]:
    """
    Displays the interactive playback menu using prompt_toolkit.prompt in a loop.
    Returns an action string (e.g., "stop", "next", "quality", "donate", "quit")
    and potentially data (e.g., new quality string).
    """
    clear_screen()  # Keep current stream info visible if possible, or re-print
    console.print(
        f"Now Playing: [highlight]{stream_url}[/highlight] ([info]{current_quality}[/info])"
    )
    console.print("-" * 30, style="dimmed")

    text = Text()
    text.append("Playback Controls:\n", style="bold white")
    text.append("  [", style="dimmed").append("S", style="menu_key").append(
        "]eplay Stream\n", style="menu_option"
    )
    if has_next:
        text.append("  [", style="dimmed").append("N", style="menu_key").append(
            "]ext Stream\n", style="menu_option"
        )
    if has_previous:
        text.append("  [", style="dimmed").append("P", style="menu_key").append(
            "]revious Stream\n", style="menu_option"
        )
    text.append("  [", style="dimmed").append("C", style="menu_key").append(
        "]hange Quality\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("M", style="menu_key").append(
        "]ain Menu (stops current stream)\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("D", style="menu_key").append(
        "]onate to Developer\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("Q", style="menu_key").append(
        "]uit StreamWatch\n", style="menu_option"
    )
    console.print(text)
    console.print("-" * 30, style="dimmed")

    try:
        # Using prompt_toolkit.prompt for single character input with history disabled
        choice = (
            prompt(
                "Playback> ",
                style=playback_menu_style,
                # bottom_toolbar=lambda: " [S]top [N]ext [P]rev [C]hange [D]onate [Q]uit", # Example toolbar
                refresh_interval=0.5,  # To allow checking player status, see core.py
            )
            .strip()
            .lower()
        )
        return (choice, None)
    except (EOFError, KeyboardInterrupt):  # Ctrl+C or Ctrl+D
        return ("s", None)  # Treat as "stop stream" and return to main menu


def select_quality_dialog(
    available_qualities: List[str], current_quality: str
) -> Optional[str]:
    """
    Shows a dialog to select a new stream quality.
    Returns the selected quality string or None if cancelled or no change.
    """
    if not available_qualities:
        message_dialog(
            title="No Qualities",
            text="Could not retrieve available qualities for this stream.",
            style=dialog_style,
        ).run()
        return None

    choices = []
    default_selection = None
    for i, quality in enumerate(
        sorted(
            available_qualities, key=lambda q: (q != "best", q != "worst", q)
        )  # Sort, with best/worst prioritized
    ):  # Sort, with best/worst prioritized
        # The value to return is the quality string itself.
        display_text = f"[{i+1}] {quality}"
        if quality == current_quality:
            display_text += " (current)"
            default_selection = quality  # Set default for radiolist_dialog

        choices.append((quality, display_text))

    if not choices:  # Should not happen if available_qualities is not empty
        message_dialog(
            title="Error",
            text="No valid quality choices to display.",
            style=dialog_style,
        ).run()
        return None

    selected_quality = radiolist_dialog(
        title="Change Stream Quality",
        text="Select new quality:",
        values=choices,
        default=default_selection,  # Pre-select the current quality
        style=dialog_style,
    ).run()

    if selected_quality and selected_quality != current_quality:
        return str(selected_quality)
    elif selected_quality == current_quality:
        console.print("Selected quality is the same as current.", style="info")
        time.sleep(1)
    return None  # Cancelled or no change


__all__ = [
    "prompt_for_filepath",
    "select_stream_dialog",
    "prompt_add_streams",
    "prompt_remove_streams_dialog",
    "prompt_main_menu_action",
    "show_playback_menu",
    "select_quality_dialog",
]
