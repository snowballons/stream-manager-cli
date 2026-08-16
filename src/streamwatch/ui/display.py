"""
StreamWatch UI Display Module

This module contains all display and presentation functions for the StreamWatch CLI application.
It handles rendering of menus, stream lists, messages, and other visual elements.
"""

import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Union

from prompt_toolkit import prompt
from rich.text import Text

from .. import config
from .styles import STREAM_DISPLAY_COLORS, console, dialog_style

# Import security utilities
try:
    from .security import safe_format_for_display, safe_format_stream_info

    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

# Import pagination utilities
try:
    from .pagination import PaginationInfo

    PAGINATION_AVAILABLE = True
except ImportError:
    PAGINATION_AVAILABLE = False

# Get a logger for this module
logger = logging.getLogger(config.APP_NAME + ".ui.display")


def clear_screen() -> None:
    """Clears the terminal screen."""
    try:
        if os.name == "nt":
            subprocess.run(["cls"], shell=True, check=False)  # nosec B602
        else:
            subprocess.run(["clear"], check=False)  # nosec B603
    except Exception:
        pass  # Ignore errors if clear command fails
    logger.debug("Screen cleared.")


def display_main_menu(live_streams_count: int) -> None:
    """Displays the main menu options."""
    logger.info(f"Displaying main menu. Live streams count: {live_streams_count}")
    console.print("------------------------------------", style="dimmed")
    console.print("Main Menu Options:", style="bold white")
    text = Text()
    if live_streams_count > 0:
        text.append("  [", style="dimmed").append("Enter", style="menu_key").append(
            "]  - Select & Play live stream\n", style="menu_option"
        )
    text.append("  [", style="dimmed").append("L", style="menu_key").append(
        "]      - List all configured streams\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("A", style="menu_key").append(
        "]      - Add new stream URL(s)\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("R", style="menu_key").append(
        "]      - Remove configured stream(s)\n", style="menu_option"
    )

    # --- ENHANCED DATABASE FEATURES ---
    text.append("  [", style="dimmed").append("I", style="menu_key").append(
        "]      - Import streams (.txt, .json, .m3u)\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("E", style="menu_key").append(
        "]      - Export streams (multiple formats)\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("T", style="menu_key").append(
        "]      - Manage stream tags\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("H", style="menu_key").append(
        "]      - Export history & analytics\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("V", style="menu_key").append(
        "]      - Recording controls\n", style="menu_option"
    )

    # --- END ENHANCED FEATURES ---

    (
        text.append("  [", style="dimmed")
        .append("P", style="menu_key")
        .append("]lay Last Stream\n", style="menu_option")
        if config.get_last_played_url()
        else None
    )
    text.append("  [", style="dimmed").append("F", style="menu_key").append(
        "]      - Refresh live stream list\n", style="menu_option"
    )
    text.append("  [", style="dimmed").append("Q", style="menu_key").append(
        "]      - Quit\n", style="menu_option"
    )
    console.print(text)
    console.print("------------------------------------", style="dimmed")


def format_viewer_count(count: Optional[int]) -> str:
    """Formats the viewer count nicely (e.g., 1234 -> 1.2K)."""
    if count is None or not isinstance(count, (int, float)):
        return ""  # Return empty string if no count is available

    if count < 1000:
        return f"{count}"
    elif count < 1_000_000:
        return f"{count / 1000:.1f}K"
    else:
        return f"{count / 1_000_000:.1f}M"


def format_stream_for_display(
    stream_info: Dict[str, Any],
    index: Optional[int] = None,
    for_prompt_toolkit: bool = False,
) -> Union[Text, str]:
    """Format stream information safely for display with XSS protection."""
    text = Text()
    colors = STREAM_DISPLAY_COLORS

    if isinstance(stream_info, dict):
        # Use safe formatting if available
        if SECURITY_AVAILABLE:
            safe_info = safe_format_stream_info(stream_info)
        else:
            # Fallback: basic string conversion
            safe_info = {
                "alias": str(stream_info.get("alias", "Unknown Stream"))[:50],
                "platform": str(stream_info.get("platform", "Unknown"))[:20],
                "username": str(stream_info.get("username", "unknown"))[:30],
                "category": str(
                    stream_info.get(
                        "category_keywords", stream_info.get("category", "N/A")
                    )
                )[:30],
                "viewer_count": stream_info.get("viewer_count", "N/A"),
            }

        if index is not None:
            text.append(f"[{index + 1}] ", style=colors["num_color"])

        # Use safe display name
        display_name = safe_info.get("alias") or safe_info.get("username", "N/A")
        text.append(display_name, style=colors["username_color"])
        text.append(f" ({safe_info['platform']})", style=colors["platform_color"])

        # Safe viewer count display
        if SECURITY_AVAILABLE:
            viewer_display = safe_info.get("viewer_count", "N/A")
        else:
            viewer_count = stream_info.get("viewer_count")
            if viewer_count is not None:
                viewer_display = format_viewer_count(viewer_count)
            else:
                viewer_display = "N/A"

        if viewer_display != "N/A":
            text.append(f" │ 👁️ {viewer_display}", style=colors["viewer_color"])

        # --- Intelligent Description Display ---
        # Use only the category field for description.
        description = stream_info.get("category")
        if not description or description == "N/A":
            description = stream_info.get("title")

        # If we still have no description, fallback to "N/A"
        if not description:
            description = "N/A"
        # Safely format and append the chosen description
        safe_description = safe_format_for_display(
            description, 60
        )  # Truncate long titles
        text.append(f" - {safe_description}", style=colors["category_color"])
    elif isinstance(stream_info, str):
        if index is not None:
            text.append(f"[{index + 1}] ", style=colors["num_color"])
        text.append(stream_info, style="dim white")
    elif (
        isinstance(stream_info, tuple) and len(stream_info) == 2
    ):  # New: Handle (index, data) for removal
        idx, data = stream_info
        text.append(f"[{idx + 1}] ", style=colors["num_color"])
        text.append(
            str(data.get("alias", data.get("url"))), style=colors["username_color"]
        )  # Show alias
        text.append(f" ({data.get('url')})", style="dimmed")  # Show URL dimmed
    else:
        text.append("Invalid stream data", style="error")

    if for_prompt_toolkit:
        return str(text)
    return text


def display_stream_list(
    stream_info_list: List[Dict[str, Any]], title: str = "--- Available Streams ---"
) -> None:
    """Displays a list of streams with their metadata (less interactive, more for general display)."""
    clear_screen()
    console.print(Text(title, style="title"))
    if not stream_info_list:
        console.print("  (No streams to display)", style="dimmed")
        console.print()
        return

    for i, stream_info in enumerate(stream_info_list):
        formatted_text = format_stream_for_display(stream_info, i)
        console.print(f"  {formatted_text}")
    console.print()


def display_urls_for_removal(
    all_streams: List[Dict[str, Any]],
    title: str = "--- Configured Streams (for removal) ---",
) -> None:
    console.print(title, style="title")
    if not all_streams:
        console.print(" (No streams to display)", style="dimmed")
        return
    for i, url in enumerate(all_streams):
        console.print(f"  {format_stream_for_display(url, i)}")


def display_paginated_stream_list(
    stream_info_list: List[Dict[str, Any]],
    pagination_info: "PaginationInfo",
    title: str = "--- Streams ---",
    show_pagination_controls: bool = True,
    clear_screen_first: bool = False,
) -> None:
    """
    Display a paginated list of streams with pagination information.

    Args:
        stream_info_list: List of streams for current page
        pagination_info: Pagination information
        title: Title to display above the list
        show_pagination_controls: Whether to show pagination controls
        clear_screen_first: Whether to clear screen before displaying
    """
    if not PAGINATION_AVAILABLE:
        # Fallback to regular display
        if clear_screen_first:
            clear_screen()
        display_stream_list(stream_info_list, title)
        return

    if clear_screen_first:
        clear_screen()

    # Display title with page info
    if pagination_info.total_pages > 1:
        page_title = f"{title} (Page {pagination_info.current_page + 1}/{pagination_info.total_pages})"
    else:
        page_title = title

    console.print(page_title, style="title")

    # Handle empty list
    if not stream_info_list:
        console.print("  (No streams to display)", style="dimmed")
        console.print()
        return

    # Display streams for current page
    for i, stream_info in enumerate(stream_info_list):
        # Calculate global index for proper numbering
        global_index = pagination_info.start_index + i
        formatted = format_stream_for_display(stream_info, index=global_index)
        console.print(f"  {formatted}")

    console.print()

    # Display pagination info and controls
    if show_pagination_controls and pagination_info.total_pages > 1:
        _display_pagination_controls(pagination_info)


def display_filter_summary(filter_summary: str) -> None:
    """
    Display active filter summary.

    Args:
        filter_summary: Summary of active filters
    """
    if filter_summary:
        console.print(f"🔍 Active filters: {filter_summary}", style="dimmed")
        console.print()


def display_pagination_help() -> None:
    """Display help for pagination controls."""
    console.print("\n📖 Pagination Controls:", style="info")
    console.print("  n, next     - Next page", style="dimmed")
    console.print("  p, prev     - Previous page", style="dimmed")
    console.print("  f, first    - First page", style="dimmed")
    console.print("  l, last     - Last page", style="dimmed")
    console.print("  s, search   - Search streams", style="dimmed")
    console.print("  cf          - Filter by category", style="dimmed")
    console.print("  pf          - Filter by platform", style="dimmed")
    console.print("  clear       - Clear all filters", style="dimmed")
    console.print()


def display_search_prompt() -> None:
    """Display search prompt information."""
    console.print(
        "🔍 Enter search term (searches alias, username, and category):", style="info"
    )
    console.print("   Leave empty to clear search filter", style="dimmed")


def display_category_filter_prompt(available_categories: List[str]) -> None:
    """
    Display category filter prompt with available categories.

    Args:
        available_categories: List of available categories
    """
    console.print("📂 Available categories:", style="info")
    if available_categories:
        for i, category in enumerate(available_categories[:10]):  # Show max 10
            console.print(f"   {i+1}. {category}", style="dimmed")
        if len(available_categories) > 10:
            console.print(
                f"   ... and {len(available_categories) - 10} more", style="dimmed"
            )
    else:
        console.print("   No categories available", style="dimmed")

    console.print("Enter category name (or leave empty to clear filter):", style="info")


def display_platform_filter_prompt(available_platforms: List[str]) -> None:
    """
    Display platform filter prompt with available platforms.

    Args:
        available_platforms: List of available platforms
    """
    console.print("🌐 Available platforms:", style="info")
    if available_platforms:
        for i, platform in enumerate(available_platforms):
            console.print(f"   {i+1}. {platform}", style="dimmed")
    else:
        console.print("   No platforms available", style="dimmed")

    console.print("Enter platform name (or leave empty to clear filter):", style="info")


def _display_pagination_controls(pagination_info: "PaginationInfo") -> None:
    """
    Display pagination controls and information.

    Args:
        pagination_info: Pagination information
    """
    # Show current position
    console.print(
        f"Showing {pagination_info.start_index + 1}-{pagination_info.end_index} "
        f"of {pagination_info.total_items} streams",
        style="dimmed",
    )

    # Show available controls
    controls = []

    if pagination_info.has_previous:
        controls.extend(["[[p]]rev", "[[f]]irst"])

    if pagination_info.has_next:
        controls.extend(["[[n]]ext", "[[l]]ast"])

    controls.extend(["[[s]]earch", "[[c]]lear filters", "[[h]]elp"])

    if controls:
        console.print(f"Controls: {' | '.join(controls)}", style="dimmed")

    console.print()


def show_message(
    message: str, style: str = "info", duration: float = 1.5, pause_after: bool = False
) -> None:
    """Displays a message for a short duration."""
    logger.info(f"Show message: {message} (style={style})")
    console.print(f"\n{message}", style=style)
    if duration > 0:
        time.sleep(duration)
    if pause_after:
        try:
            prompt("\nPress Enter to continue...", style=dialog_style)
        except (EOFError, KeyboardInterrupt):
            pass


__all__ = [
    "clear_screen",
    "display_main_menu",
    "display_stream_list",
    "format_stream_for_display",
    "format_viewer_count",
    "display_urls_for_removal",
    "show_message",
]
