"""Playback control functionality for StreamWatch application."""

import logging
import time
import webbrowser
from typing import Any, Dict, List

from . import config, player, stream_utils, ui

logger = logging.getLogger(config.APP_NAME + ".playback_controller")


class PlaybackController:
    """Handles playback session management for the StreamWatch application."""

    def __init__(self) -> None:
        """Initialize the PlaybackController."""
        pass

    def start_playback_session(
        self,
        initial_stream_info: Dict[str, Any],
        initial_quality: str,
        all_live_streams_list: List[Dict[str, Any]],
    ) -> str:
        """
        Manages an active playback session with interactive controls.

        Args:
            initial_stream_info: Stream information dictionary
            initial_quality: Initial quality setting
            all_live_streams_list: List of all live streams for navigation

        Returns:
            Action string indicating what to do next
        """
        current_stream_info = initial_stream_info
        current_quality = initial_quality
        player_process = None
        user_intent_direction = 0  # 0: none, 1: next, -1: previous

        try:
            current_playing_index = [
                idx
                for idx, s_info in enumerate(all_live_streams_list)
                if s_info["url"] == current_stream_info["url"]
            ][0]
        except IndexError:
            logger.error(
                "Could not find current stream in live list. Aborting playback session."
            )
            ui.console.print(
                "[error]Could not find current stream in live list. Aborting playback session.[/error]"
            )
            return "return_to_main"

        while True:
            if not player_process:
                logger.info(
                    f"Attempting to launch stream: {current_stream_info['url']}"
                )

                # --- QUALITY SELECTION LOGIC ---
                available_qualities = player.fetch_available_qualities(
                    current_stream_info["url"]
                )
                if available_qualities:
                    final_quality = stream_utils.select_best_available_quality(
                        current_quality, available_qualities
                    )
                    if final_quality != current_quality:
                        logger.info(
                            f"Preferred quality '{current_quality}' not available. Fell back to '{final_quality}'."
                        )
                        ui.console.print(
                            f"Quality [bold yellow]{current_quality}[/bold yellow] not found, falling back to [bold green]{final_quality}[/bold green]."
                        )
                        current_quality = final_quality
                else:
                    logger.warning(
                        f"Could not fetch available qualities for {current_stream_info['url']}. Using preferred quality '{current_quality}'."
                    )
                    final_quality = current_quality
                # --- END QUALITY SELECTION ---

                # --- PRE-PLAYBACK HOOK ---
                player.execute_hook("pre", current_stream_info, final_quality)

                player_process = player.launch_player_process(
                    current_stream_info["url"], final_quality
                )

                if player_process:
                    # --- Successful Launch ---
                    user_intent_direction = 0  # Reset intent after a successful launch
                    config.set_last_played_url(current_stream_info["url"])
                    logger.info(
                        f"Successfully launched. Last played URL set to: {current_stream_info['url']}"
                    )
                else:
                    # --- POST-PLAYBACK HOOK ON LAUNCH FAILURE ---
                    player.execute_hook("post", current_stream_info, final_quality)
                    # --- Launch Failed ---
                    logger.warning(
                        f"Failed to launch player for {current_stream_info['url']}."
                    )

                    # If this was the very first stream the user tried to play, and it failed, try next stream
                    if user_intent_direction == 0:
                        ui.console.print(
                            f"Failed to start [info]{current_stream_info['username']}[/info]. Trying next stream...",
                            style="warning",
                        )
                        user_intent_direction = 1  # Set direction to next

                    # Otherwise, we were trying to auto-skip, so continue that process.
                    ui.console.print(
                        f"Skipping unavailable stream: [info]{current_stream_info['username']}[/info]",
                        style="dimmed",
                    )

                    # Find next playable stream
                    found_playable = False
                    for _ in range(len(all_live_streams_list)):
                        if user_intent_direction == 1:  # Trying to find next
                            current_playing_index = (current_playing_index + 1) % len(
                                all_live_streams_list
                            )
                        elif user_intent_direction == -1:  # Trying to find previous
                            current_playing_index = (
                                current_playing_index - 1 + len(all_live_streams_list)
                            ) % len(all_live_streams_list)

                        current_stream_info = all_live_streams_list[
                            current_playing_index
                        ]
                        ui.console.print(
                            f"Trying next: [info]{current_stream_info['username']}[/info]",
                            style="dimmed",
                        )

                        # Attempt to launch the new candidate
                        player_process = player.launch_player_process(
                            current_stream_info["url"], current_quality
                        )
                        if player_process:
                            found_playable = True
                            break

                    if not found_playable:
                        ui.show_message(
                            "Could not find any playable streams in the current direction.",
                            style="error",
                            duration=2,
                            pause_after=True,
                        )
                        return "return_to_main"

                    continue

            # --- Show Menu and Get User Action ---
            is_navigation_possible = len(all_live_streams_list) > 1
            action, data = ui.show_playback_menu(
                current_stream_info["url"],
                current_quality,
                is_navigation_possible,
                is_navigation_possible,
            )

            # --- Handle User Action ---
            # Handle all actions through the existing function
            action_result = self.handle_playback_controls(
                action,
                data,
                current_stream_info,
                current_quality,
                all_live_streams_list,
                current_playing_index,
                is_navigation_possible,
                player_process,
            )

            # --- Immediate Quit Handler ---
            # Handle the 'quit' action immediately to ensure a clean exit.
            if action_result.get("return_action") == "quit_application":
                logger.info(
                    "User requested quit from playback. Terminating session and exiting."
                )
                if player_process:
                    player.terminate_player_process(player_process)
                    player.execute_hook("post", current_stream_info, current_quality)
                # We must exit the entire application here.
                # Returning the string causes issues down the line.
                import sys

                ui.clear_screen()
                ui.console.print("Exiting StreamWatch. Goodbye!", style="success")
                sys.exit(0)
            # --- End of Immediate Quit Handler ---

            # --- Handle State Updates and Termination ---

            # Check if the current stream needs to be stopped for the next action
            if action in [
                "s",
                "stop",
                "n",
                "next",
                "p",
                "previous",
                "c",
                "change_quality",
            ]:
                if player_process:
                    player.terminate_player_process(player_process)
                    player.execute_hook("post", current_stream_info, current_quality)
                player_process = None  # Invalidate the process variable immediately

            # Update state from the action result
            if action_result.get("new_stream_info"):
                current_stream_info = action_result["new_stream_info"]
            if action_result.get("new_quality"):
                current_quality = action_result["new_quality"]
            if action_result.get("new_index") is not None:
                current_playing_index = action_result["new_index"]
            if action_result.get("new_player_process") is not None:
                player_process = action_result["new_player_process"]
            if action_result.get("user_intent_direction") is not None:
                user_intent_direction = action_result["user_intent_direction"]

            # If the action was 'donate', simply continue the loop without changing state
            if action == "d" or action == "donate":
                time.sleep(0.1)  # Small pause to prevent rapid looping
                continue

            # Handle actions that should end the entire playback session
            if action_result["terminate"]:
                if player_process:  # Ensure player is stopped before exiting
                    player.terminate_player_process(player_process)
                    player.execute_hook("post", current_stream_info, current_quality)
                return action_result["return_action"]

    def handle_playback_controls(
        self,
        action: str,
        data: Any,
        current_stream_info: Dict[str, Any],
        current_quality: str,
        all_live_streams_list: List[Dict[str, Any]],
        current_playing_index: int,
        is_navigation_possible: bool,
        player_process: Any,
    ) -> Dict[str, Any]:
        """
        Handle playback control actions.

        Returns:
            Dictionary with action results and state changes
        """
        result = {
            "terminate": False,
            "return_action": None,
            "new_stream_info": None,
            "new_quality": None,
            "new_index": None,
            "new_player_process": None,
            "user_intent_direction": None,
        }

        if action == "s" or action == "stop":  # 'stop' now means 'replay'
            logger.info("User requested to replay the current stream.")
            result[
                "new_player_process"
            ] = None  # This signals the main loop to re-launch
            result["user_intent_direction"] = 0  # Reset to treat as fresh attempt

        elif action == "m" or action == "main_menu":
            logger.info("User returned to main menu from playback.")
            ui.console.print(
                "Stopping stream and returning to main menu...", style="info"
            )
            result["terminate"] = True
            result["return_action"] = "return_to_main"

        elif action == "c" or action == "change_quality":
            logger.info("User requested to change stream quality.")
            available_qualities = player.fetch_available_qualities(
                current_stream_info["url"]
            )
            if available_qualities:
                new_quality = ui.select_quality_dialog(
                    available_qualities, current_quality
                )
                if new_quality:
                    logger.info(f"User changed quality to {new_quality}.")
                    # Set new player process to None to trigger restart with new quality
                    result["new_player_process"] = None
                    result["new_quality"] = new_quality
                    result["user_intent_direction"] = 0
            else:
                logger.warning(
                    f"Could not fetch qualities for {current_stream_info['url']}"
                )
                ui.console.print(
                    f"Could not fetch qualities for {current_stream_info['url']}",
                    style="warning",
                )
                time.sleep(1.5)
                # Continue playback with current settings

        elif action == "n" or action == "next":
            if is_navigation_possible:
                logger.info("User requested next stream.")
                # Use modulo arithmetic for circular list
                new_index = (current_playing_index + 1) % len(all_live_streams_list)
                new_stream_info = all_live_streams_list[new_index]
                result["new_stream_info"] = new_stream_info
                result["new_index"] = new_index
                result["new_player_process"] = None
                result["user_intent_direction"] = 1
                result["new_quality"] = config.get_streamlink_quality()
            else:
                ui.console.print("No next stream available.", style="warning")
                time.sleep(1)

        elif action == "p" or action == "previous":
            if is_navigation_possible:
                logger.info("User requested previous stream.")
                # Modulo arithmetic for circular list (works for negative numbers in Python)
                new_index = (
                    current_playing_index - 1 + len(all_live_streams_list)
                ) % len(all_live_streams_list)
                new_stream_info = all_live_streams_list[new_index]
                result["new_stream_info"] = new_stream_info
                result["new_index"] = new_index
                result["new_player_process"] = None
                result["user_intent_direction"] = -1
                result["new_quality"] = config.get_streamlink_quality()
            else:
                ui.console.print("No previous stream available.", style="warning")
                time.sleep(1)

        elif action == "d" or action == "donate":
            try:
                donation_url = config.get_donation_link()
                logger.info(f"User opened donation link: {donation_url}")
                ui.console.print(
                    f"Opening donation link: [link={donation_url}]{donation_url}[/link]",
                    style="info",
                )
                webbrowser.open(donation_url)
                time.sleep(1)
                # Continue playback - don't terminate or modify player process
            except Exception as e:
                logger.error(f"Could not open donation link: {e}", exc_info=True)
                ui.console.print(f"[error]Could not open donation link: {e}[/error]")
                time.sleep(1.5)
                # Continue playback even if donation link fails

        elif action == "q" or action == "quit":
            logger.info("User quit application from playback session.")
            result["terminate"] = True
            result["return_action"] = "quit_application"

        else:
            # If no user action was taken, check if the player is still running.
            if player_process and player_process.poll() is not None:
                logger.warning("Player process has exited unexpectedly.")
                ui.console.print(
                    "\n[warning]Player exited unexpectedly.[/warning]", style="warning"
                )
                # This should terminate the session and return to the main menu
                result["terminate"] = True
                result["return_action"] = "return_to_main"
            time.sleep(0.1)

        return result

    def stop_playback(
        self, player_process: Any, stream_info: Dict[str, Any], quality: str
    ) -> None:
        """Stop the current playback session."""
        if player_process:
            player.terminate_player_process(player_process)
            player.execute_hook("post", stream_info, quality)
