import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import config, ui
from .enhanced_database import EnhancedStreamDatabase
from .models import StreamInfo
from .stream_utils import parse_url_metadata

logger = logging.getLogger(config.APP_NAME + ".stream_manager")


class StreamManager:
    """Handles stream CRUD operations with enhanced SQLite database."""

    def __init__(self, database: EnhancedStreamDatabase):
        """Initialize the StreamManager with enhanced database dependency."""
        self.db = database

    def add_streams(self) -> Tuple[bool, str]:
        """Handle adding new streams to the database via the UI."""
        new_streams_data = ui.prompt_add_streams()
        if not new_streams_data:
            logger.info("Add operation cancelled or no URLs entered.")
            return False, "Add operation cancelled or no URLs entered."

        added_count = 0
        for stream_data in new_streams_data:
            try:
                url = stream_data["url"]
                alias = stream_data["alias"]

                # Parse the URL to get platform and a default username
                parsed_info = parse_url_metadata(url)
                platform = parsed_info.get("platform", "Unknown")
                username = parsed_info.get("username", "unknown_stream")

                # If no alias was provided by the user, use the username as the default
                if not alias:
                    alias = username

                # Create a complete, validated StreamInfo object
                stream = StreamInfo(
                    url=url, alias=alias, platform=platform, username=username
                )
                self.db.save_stream(stream)
                added_count += 1
            except Exception as e:
                logger.warning(f"Could not add stream {stream_data.get('url')}: {e}")
                ui.console.print(
                    f"[error]Failed to add stream '{stream_data.get('url')}': {e}[/error]"
                )

        if added_count > 0:
            message = f"Successfully added {added_count} new stream(s)."
            return True, message
        else:
            return False, "No new streams were added."

    def remove_streams(self) -> Tuple[bool, str]:
        """Handle removing streams from the database via the UI."""
        all_streams = self.db.load_streams()
        all_streams_dicts = [s.model_dump() for s in all_streams]

        indices_to_remove = ui.prompt_remove_streams_dialog(all_streams_dicts)

        if indices_to_remove is not None and indices_to_remove:
            removed_count = 0
            for index in indices_to_remove:
                if 0 <= index < len(all_streams):
                    stream_to_remove = all_streams[index]
                    if self.db.delete_stream(stream_to_remove.url):
                        removed_count += 1

            message = f"Successfully removed {removed_count} stream(s)."
            return True, message
        elif indices_to_remove is None:
            return False, "Remove operation cancelled."
        else:
            return False, "No valid streams selected for removal."

    def list_streams(self) -> None:
        """Display all configured streams from the database."""
        ui.clear_screen()
        all_streams = self.db.load_streams()
        all_streams_dicts = [s.model_dump() for s in all_streams]
        ui.display_stream_list(
            all_streams_dicts, title="--- All Configured Streams ---"
        )
        ui.show_message("", duration=0, pause_after=True)

    def import_streams(self) -> Tuple[bool, str]:
        """Handle importing streams from various file formats."""
        filepath_str = ui.prompt_for_filepath(
            "Enter path of file to import (.txt, .json, .m3u): "
        )
        if not filepath_str:
            return False, "Import cancelled."

        try:
            source_path = Path(filepath_str).expanduser()
            if not source_path.is_file():
                return False, f"Import file not found at: {source_path}"

            # Determine file type and import accordingly
            file_ext = source_path.suffix.lower()

            if file_ext == ".json":
                result = self.db.import_from_json(source_path, merge_mode="skip")
                if result["success"]:
                    imported = result.get("imported", 0)
                    skipped = result.get("skipped", 0)
                    message = f"Successfully imported {imported} stream(s)"
                    if skipped > 0:
                        message += f" ({skipped} skipped as duplicates)"
                    return True, message
                else:
                    return (
                        False,
                        f"JSON import failed: {result.get('error', 'Unknown error')}",
                    )

            elif file_ext == ".m3u":
                result = self.db.import_from_m3u(source_path)
                if result["success"]:
                    imported = result.get("imported", 0)
                    return (
                        True,
                        f"Successfully imported {imported} stream(s) from M3U playlist",
                    )
                else:
                    return (
                        False,
                        f"M3U import failed: {result.get('error', 'Unknown error')}",
                    )

            else:
                # Default to text file import (one URL per line)
                return self._import_from_text_file(source_path)

        except Exception as e:
            message = f"An error occurred during import: {e}"
            logger.error(message, exc_info=True)
            return False, message

    def _import_from_text_file(self, source_path: Path) -> Tuple[bool, str]:
        """Import streams from text file (one URL per line)."""
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                urls_to_import = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]

            if not urls_to_import:
                return False, "Import file is empty or contains no valid lines."

            imported_count = 0
            for url in urls_to_import:
                try:
                    parsed_info = parse_url_metadata(url)
                    platform = parsed_info.get("platform", "Unknown")
                    username = parsed_info.get("username", "unknown_stream")
                    alias = (
                        username  # For imports, the username is the best default alias
                    )

                    stream_info = StreamInfo(
                        url=url, alias=alias, platform=platform, username=username
                    )
                    self.db.save_stream(stream_info)
                    imported_count += 1
                except Exception as e:
                    logger.warning(f"Could not import stream URL {url}: {e}")

            return True, f"Successfully imported {imported_count} stream(s)."

        except Exception as e:
            raise e

    def export_streams(self) -> Tuple[bool, str]:
        """Handle exporting streams with multiple format options."""
        # Get export format choice
        export_formats = {
            "1": ("json", "JSON with full metadata"),
            "2": ("csv", "CSV spreadsheet format"),
            "3": ("xml", "XML structured format"),
            "4": ("m3u", "M3U playlist (live streams only)"),
            "5": ("analytics", "Analytics report"),
            "6": ("backup", "Complete database backup"),
        }

        ui.console.print("\n[bold]Export Formats:[/bold]")
        for key, (format_type, description) in export_formats.items():
            ui.console.print(f"  {key}. {description}")

        choice = ui.console.input("\nSelect export format (1-6): ").strip()

        if choice not in export_formats:
            return False, "Invalid export format selected."

        format_type, _ = export_formats[choice]

        # Get file path
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        default_filename = f"~/streamwatch_export_{timestamp}.{format_type}"
        if format_type == "backup":
            default_filename = f"~/streamwatch_backup_{timestamp}.db"

        filepath_str = ui.prompt_for_filepath(
            f"Enter path to save {format_type.upper()} export: ",
            default_filename=default_filename,
        )
        if not filepath_str:
            return False, "Export cancelled."

        try:
            destination_path = Path(filepath_str).expanduser()
            destination_path.parent.mkdir(parents=True, exist_ok=True)

            # Perform export based on format
            if format_type == "json":
                # Ask for additional options
                include_history = (
                    ui.console.input("Include stream history? (y/N): ")
                    .lower()
                    .startswith("y")
                )
                include_analytics = (
                    ui.console.input("Include analytics data? (y/N): ")
                    .lower()
                    .startswith("y")
                )

                result = self.db.export_to_json(
                    destination_path, include_history, include_analytics
                )

            elif format_type == "csv":
                include_stats = (
                    ui.console.input("Include statistics? (Y/n): ").lower() != "n"
                )
                result = self.db.export_to_csv(destination_path, include_stats)

            elif format_type == "xml":
                result = self.db.export_to_xml(destination_path)

            elif format_type == "m3u":
                live_only = (
                    ui.console.input("Export live streams only? (Y/n): ").lower() != "n"
                )
                result = self.db.export_to_m3u(destination_path, live_only)

            elif format_type == "analytics":
                days_str = ui.console.input(
                    "Number of days to analyze (default 30): "
                ).strip()
                days = int(days_str) if days_str.isdigit() else 30
                result = self.db.export_analytics_report(destination_path, days)

            elif format_type == "backup":
                result = self.db.create_backup(destination_path)

            if result["success"]:
                streams_count = result.get(
                    "streams_exported", result.get("streams_analyzed", "N/A")
                )
                file_size = result["file_size"]
                size_mb = file_size / (1024 * 1024)

                message = f"Successfully exported to {destination_path}"
                if streams_count != "N/A":
                    message += f"\nStreams: {streams_count}"
                message += f"\nFile size: {size_mb:.2f} MB"

                logger.info(message)
                return True, message
            else:
                return False, f"Export failed: {result.get('error', 'Unknown error')}"

        except Exception as e:
            message = f"An error occurred during export: {e}"
            logger.error(message, exc_info=True)
            return False, message

    def show_export_history(self) -> None:
        """Display export history."""
        ui.clear_screen()
        history = self.db.get_export_history(limit=20)

        if not history:
            ui.console.print("No export history found.")
            return

        ui.console.print("[bold]Export History (Last 20):[/bold]\n")

        for entry in history:
            export_type = entry["export_type"].upper()
            file_path = entry["file_path"]
            stream_count = entry["stream_count"]
            file_size_mb = entry["file_size_bytes"] / (1024 * 1024)
            exported_at = entry["exported_at"]

            ui.console.print(f"[cyan]{export_type}[/cyan] - {exported_at}")
            ui.console.print(f"  📁 {file_path}")
            ui.console.print(f"  📊 {stream_count} streams, {file_size_mb:.2f} MB")

            if entry.get("metadata"):
                metadata = entry["metadata"]
                if "include_history" in metadata:
                    ui.console.print(
                        f"  📈 History: {metadata['include_history']}, Analytics: {metadata.get('include_analytics', False)}"
                    )
                elif "live_only" in metadata:
                    ui.console.print(f"  🔴 Live only: {metadata['live_only']}")
                elif "days" in metadata:
                    ui.console.print(f"  📅 Period: {metadata['days']} days")

            ui.console.print()

        ui.show_message("", duration=0, pause_after=True)

    def manage_tags(self) -> None:
        """Manage stream tags."""
        while True:
            ui.clear_screen()
            ui.console.print("[bold]Stream Tag Management[/bold]\n")
            ui.console.print("1. Add tag to stream")
            ui.console.print("2. Remove tag from stream")
            ui.console.print("3. View stream tags")
            ui.console.print("4. Back to main menu")

            choice = ui.console.input("\nSelect option (1-4): ").strip()

            if choice == "1":
                self._add_tag_to_stream()
            elif choice == "2":
                self._remove_tag_from_stream()
            elif choice == "3":
                self._view_stream_tags()
            elif choice == "4":
                break
            else:
                ui.console.print("[red]Invalid choice. Please try again.[/red]")
                time.sleep(1)

    def _add_tag_to_stream(self) -> None:
        """Add a tag to a stream."""
        streams = self.db.load_streams()
        if not streams:
            ui.console.print("[yellow]No streams configured.[/yellow]")
            time.sleep(2)
            return

        # Show streams
        ui.console.print("\n[bold]Select a stream:[/bold]")
        for i, stream in enumerate(streams):
            ui.console.print(f"{i + 1}. {stream.alias} ({stream.platform})")

        try:
            choice = int(ui.console.input("\nEnter stream number: ")) - 1
            if 0 <= choice < len(streams):
                selected_stream = streams[choice]

                tag_name = ui.console.input("Enter tag name: ").strip()
                if tag_name:
                    color = (
                        ui.console.input("Enter tag color (default #007acc): ").strip()
                        or "#007acc"
                    )

                    self.db.add_stream_tag(selected_stream.url, tag_name, color)
                    ui.console.print(
                        f"[green]Added tag '{tag_name}' to {selected_stream.alias}[/green]"
                    )
                else:
                    ui.console.print("[red]Tag name cannot be empty.[/red]")
            else:
                ui.console.print("[red]Invalid stream selection.[/red]")
        except (ValueError, IndexError):
            ui.console.print("[red]Invalid input.[/red]")

        time.sleep(2)

    def _remove_tag_from_stream(self) -> None:
        """Remove a tag from a stream."""
        streams = self.db.load_streams()
        if not streams:
            ui.console.print("[yellow]No streams configured.[/yellow]")
            time.sleep(2)
            return

        # Show streams with tags
        ui.console.print("\n[bold]Select a stream:[/bold]")
        for i, stream in enumerate(streams):
            tags = self.db.get_stream_tags(stream.url)
            tag_names = [tag["name"] for tag in tags]
            tag_str = f" [Tags: {', '.join(tag_names)}]" if tag_names else " [No tags]"
            ui.console.print(f"{i + 1}. {stream.alias} ({stream.platform}){tag_str}")

        try:
            choice = int(ui.console.input("\nEnter stream number: ")) - 1
            if 0 <= choice < len(streams):
                selected_stream = streams[choice]
                tags = self.db.get_stream_tags(selected_stream.url)

                if not tags:
                    ui.console.print("[yellow]This stream has no tags.[/yellow]")
                    time.sleep(2)
                    return

                ui.console.print(f"\n[bold]Tags for {selected_stream.alias}:[/bold]")
                for i, tag in enumerate(tags):
                    ui.console.print(f"{i + 1}. {tag['name']}")

                tag_choice = int(ui.console.input("\nEnter tag number to remove: ")) - 1
                if 0 <= tag_choice < len(tags):
                    tag_to_remove = tags[tag_choice]["name"]
                    if self.db.remove_stream_tag(selected_stream.url, tag_to_remove):
                        ui.console.print(
                            f"[green]Removed tag '{tag_to_remove}' from {selected_stream.alias}[/green]"
                        )
                    else:
                        ui.console.print("[red]Failed to remove tag.[/red]")
                else:
                    ui.console.print("[red]Invalid tag selection.[/red]")
            else:
                ui.console.print("[red]Invalid stream selection.[/red]")
        except (ValueError, IndexError):
            ui.console.print("[red]Invalid input.[/red]")

        time.sleep(2)

    def _view_stream_tags(self) -> None:
        """View all stream tags."""
        streams = self.db.load_streams()
        if not streams:
            ui.console.print("[yellow]No streams configured.[/yellow]")
            time.sleep(2)
            return

        ui.console.print("\n[bold]Stream Tags:[/bold]\n")

        for stream in streams:
            tags = self.db.get_stream_tags(stream.url)
            if tags:
                ui.console.print(f"[cyan]{stream.alias}[/cyan] ({stream.platform})")
                for tag in tags:
                    ui.console.print(
                        f"  • {tag['name']} [color={tag['color']}]●[/color]"
                    )
                ui.console.print()

        ui.show_message("", duration=0, pause_after=True)

    def load_streams(self) -> List[Dict[str, Any]]:
        """Load all streams from the database and returns them as dicts."""
        all_streams = self.db.load_streams()
        return [s.model_dump() for s in all_streams]

    def get_stream_count(self) -> int:
        """Get the total number of configured streams from the database."""
        return len(self.db.load_streams())
