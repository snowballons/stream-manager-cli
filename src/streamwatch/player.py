import json  # For fetching qualities
import logging  # Import logging
import subprocess
import time
from typing import Any, Dict, List, Optional

from . import config, ui

# from . import stream_checker # We might put fetch_available_qualities here or in player.py

# Get a logger for this module
logger = logging.getLogger(config.APP_NAME + ".player")


# --- NEW HOOK EXECUTION FUNCTION ---
def execute_hook(hook_type: str, stream_info: Dict[str, Any], quality: str) -> None:
    """
    Executes a pre or post-playback hook script if configured.

    Args:
        hook_type: 'pre' or 'post'
        stream_info: The dictionary of the stream being played
        quality: The quality the stream is being played at
    """
    if hook_type == "pre":
        hook_path_str = config.get_pre_playback_hook()
    elif hook_type == "post":
        hook_path_str = config.get_post_playback_hook()
    else:
        return  # Invalid hook type

    if not hook_path_str:
        return  # No hook configured for this type

    from pathlib import Path

    hook_path = Path(hook_path_str).expanduser()

    if not hook_path.is_file():
        logger.warning(f"Hook script not found at configured path: {hook_path}")
        return

    # Construct the command with arguments
    command = [str(hook_path)]
    # Pass stream info as arguments. Ensure values are strings and handle None.
    command.append(stream_info.get("url", ""))
    command.append(stream_info.get("alias", ""))
    command.append(stream_info.get("username", ""))
    command.append(stream_info.get("platform", ""))
    command.append(quality or "")

    logger.info(f"Executing {hook_type}-playback hook: {' '.join(command)}")
    ui.console.print(
        f"Executing {hook_type}-playback hook: [dim]{hook_path.name}[/dim]"
    )

    try:
        # Run the hook script as a non-blocking background process.
        # This prevents a long-running hook from delaying stream playback.
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(
            f"Failed to execute {hook_type}-playback hook script.", exc_info=True
        )
        ui.console.print(f"[error]Error running hook script: {e}[/error]")


# --- Configuration for Reconnection (can be removed if not used) ---
# RECONNECTION_ATTEMPT_DURATION = 30  # seconds
# RECONNECTION_CHECK_INTERVAL = 5     # seconds
# RETRYABLE_ERROR_PATTERNS = [
#     re.compile(r"failed to reload playlist", re.IGNORECASE),
#     re.compile(r"read timeout", re.IGNORECASE),
#     re.compile(r"stream ended", re.IGNORECASE),
#     re.compile(r"tssegmenter: abrupt segment loss", re.IGNORECASE),
# ]


def launch_player_process(url_to_play: str, quality: str) -> Optional[subprocess.Popen]:
    """
    Launches streamlink and the player as a background process.

    Args:
        url_to_play: The stream URL to play
        quality: The quality setting for the stream

    Returns:
        The subprocess.Popen object or None if launch fails
    """
    ui.console.print(
        f"Launching: [info]{url_to_play}[/info] at [info]{quality}[/info] quality..."
    )
    logger.info(f"Launching player for {url_to_play} at quality {quality}")

    command = ["streamlink"]
    if config.get_twitch_disable_ads() and "twitch.tv" in url_to_play:
        command.append("--twitch-disable-ads")

    # Add player configuration
    player_name = config.get_streamlink_player()
    if player_name:
        command.extend(["--player", player_name])

    command.extend(
        [
            url_to_play,
            quality,
        ]
    )

    try:
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)  # Give a brief moment for streamlink/player to start or fail fast
        if process.poll() is not None:  # Check if it exited immediately
            logger.error(
                f"Failed to launch player for {url_to_play}. Streamlink exited early."
            )
            ui.console.print(
                f"[error]Failed to launch player for {url_to_play}. Streamlink exited early.[/error]"
            )
            return None
        logger.info("Player launched successfully.")
        ui.console.print(
            "[success]Player launched.[/success] Terminal controls are now active."
        )
        return process
    except FileNotFoundError:
        logger.critical("streamlink command not found. Cannot play stream.")
        ui.console.print(
            "[error]streamlink command not found. Cannot play stream.[/error]"
        )
        return None
    except Exception as e:
        logger.exception(f"Error launching player for {url_to_play}")
        ui.console.print(f"[error]Error launching player: {e}[/error]")
        return None


def terminate_player_process(process: Optional[subprocess.Popen]) -> None:
    """Safely terminates the player process.

    Args:
        process: The subprocess.Popen object to terminate, or None
    """
    if process and process.poll() is None:  # If process exists and is running
        ui.console.print("Stopping player...", style="info")
        try:
            process.terminate()  # Ask nicely first
            process.wait(timeout=1)  # Wait for it to terminate
        except subprocess.TimeoutExpired:
            ui.console.print(
                "Player did not terminate gracefully, forcing kill...", style="warning"
            )
            process.kill()  # Force kill
            process.wait(timeout=1)
        except Exception as e:
            ui.console.print(f"[error]Error terminating player: {e}[/error]")
        ui.console.print("Player stopped.", style="success")


def fetch_available_qualities(url_to_check: str) -> Optional[List[str]]:
    """
    Fetches available stream qualities for a given URL using streamlink.

    Args:
        url_to_check: The stream URL to check for available qualities

    Returns:
        List of quality strings (e.g., ['720p', 'best', '480p']) or None if failed
    """
    ui.console.print(
        f"Fetching available qualities for [info]{url_to_check}[/info]...",
        style="dimmed",
    )
    logger.info(f"Fetching available qualities for {url_to_check}")
    command = ["streamlink", "--json", url_to_check]
    if config.get_twitch_disable_ads() and "twitch.tv" in url_to_check:
        command.insert(1, "--twitch-disable-ads")

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=config.get_streamlink_timeout_metadata(),
            check=False,
        )
        if process.returncode == 0 and process.stdout:
            data = json.loads(process.stdout)
            if "streams" in data and isinstance(data["streams"], dict):
                qualities = [
                    q
                    for q in data["streams"].keys()
                    if q != "worst-unfiltered" and q != "best-unfiltered"
                ]
                if not qualities and "best" in data["streams"]:
                    return ["best"]
                return qualities if qualities else None
            else:
                logger.warning(
                    f"No valid streams found in streamlink output for {url_to_check}"
                )
                return None
        else:
            logger.warning(f"streamlink did not return valid output for {url_to_check}")
            return None
    except Exception:
        logger.exception(f"Error fetching available qualities for {url_to_check}")
        return None
