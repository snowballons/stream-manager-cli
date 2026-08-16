import configparser
import logging  # Import logging
import os
from pathlib import Path
from typing import Dict, Optional

# --- Core Application Details ---
APP_NAME = "streamwatch"  # Renamed from stream-manager-cli

# Get a logger for this module
logger = logging.getLogger(APP_NAME + ".config")

# --- Default Configuration Values ---
DEFAULT_CONFIG: Dict[str, Dict[str, str]] = {
    "Streamlink": {
        "quality": "best",
        "timeout_liveness": "10",  # seconds for initial liveness check
        "timeout_metadata": "15",  # seconds for fetching JSON metadata
        "max_workers_liveness": "4",
        "max_workers_metadata": "2",  # Often fewer streams need metadata fetch
        "twitch_disable_ads": "true",
        "player": "mpv",  # Default media player
    },
    "Resilience": {
        # Retry configuration
        "retry_max_attempts": "3",  # Maximum retry attempts
        "retry_base_delay": "1.0",  # Base delay in seconds
        "retry_max_delay": "60.0",  # Maximum delay in seconds
        "retry_exponential_base": "2.0",  # Exponential backoff multiplier
        "retry_jitter": "true",  # Add random jitter
        # Circuit breaker configuration
        "circuit_breaker_failure_threshold": "5",  # Failures before opening circuit
        "circuit_breaker_recovery_timeout": "60.0",  # Recovery timeout in seconds
        "circuit_breaker_success_threshold": "2",  # Successes needed to close circuit
        "circuit_breaker_enabled": "true",  # Enable circuit breaker pattern
    },
    "Cache": {
        "enabled": "true",  # Enable/disable caching
        "ttl_seconds": "300",  # Cache TTL in seconds (5 minutes)
        "auto_cleanup": "true",  # Automatically clean up expired entries
        "cleanup_interval": "600",  # Cleanup interval in seconds (10 minutes)
    },
    "RateLimit": {
        "enabled": "true",  # Enable/disable rate limiting
        "global_requests_per_second": "8.0",  # Global rate limit (requests per second)
        "global_burst_capacity": "15",  # Global burst capacity
        # Platform-specific rate limits
        "twitch_requests_per_second": "3.0",  # Twitch rate limit
        "twitch_burst_capacity": "8",  # Twitch burst capacity
        "youtube_requests_per_second": "2.0",  # YouTube rate limit
        "youtube_burst_capacity": "6",  # YouTube burst capacity
        "kick_requests_per_second": "4.0",  # Kick rate limit
        "kick_burst_capacity": "10",  # Kick burst capacity
        "default_requests_per_second": "2.0",  # Default platform rate limit
        "default_burst_capacity": "5",  # Default platform burst capacity
    },
    "Interface": {
        # Color settings could go here later
        # 'color_live': 'green',
        # 'color_username': 'cyan',
        "refresh_interval": "2.0",
        "show_offline_streams": "false",
        "streams_per_page": "20",
        "enable_search": "true",
        "enable_category_filter": "true",
        "enable_platform_filter": "true",
    },
    "Memory": {
        "metadata_cache_size": "100",
        "lazy_load_threshold": "50",
    },
    "Recording": {
        "enabled": "true",  # Enable recording feature
        "output_directory": "",  # Default to ~/Videos/StreamWatch
        "filename_template": "{platform}_{username}_{date}_{time}.{ext}",
        "default_format": "mp4",  # Default container format
        "quality": "best",  # Recording quality (can differ from playback)
        "max_file_size": "0",  # Max file size in MB (0 = unlimited)
        "max_duration": "0",  # Max duration in minutes (0 = unlimited)
        "auto_split": "false",  # Auto-split large files
        "split_size": "1000",  # Split size in MB
    },
    "Misc": {
        "donation_link": "https://buymeacoffee.com/snowballons",  # Your actual link
        "first_run_completed": "false",  # For First-Time UX
        "last_played_url": "",  # Add this
        "pre_playback_hook": "",  # NEW: Path to a script to run before playback
        "post_playback_hook": "",  # NEW: Path to a script to run after playback
    },
}


# --- Paths ---
def get_user_config_dir() -> Path:
    """Gets the platform-specific user configuration directory for the app."""
    if os.name == "nt":  # Windows
        app_data = os.getenv("APPDATA")
        if app_data:
            return Path(app_data) / APP_NAME
    else:  # Linux, macOS, etc.
        xdg_config_home = os.getenv("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home) / APP_NAME
        else:
            return Path.home() / ".config" / APP_NAME
    return Path(Path.home(), f".{APP_NAME}")  # Fallback


USER_CONFIG_DIR = get_user_config_dir()
CONFIG_FILE_PATH = USER_CONFIG_DIR / "config.ini"
STREAMS_FILE_PATH = USER_CONFIG_DIR / "streams.json"  # Keep this as is

# --- Config Loading and Management ---
config_parser = configparser.ConfigParser()


def create_default_config_file() -> bool:
    """Creates the config.ini file with default values if it doesn't exist.

    Returns:
        True if file was created, False if it already existed
    """
    if not CONFIG_FILE_PATH.exists():
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        temp_parser = configparser.ConfigParser()
        for section, options in DEFAULT_CONFIG.items():
            temp_parser[section] = {}
            for key, value in options.items():
                temp_parser[section][key] = str(value)

        try:
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as configfile:
                temp_parser.write(configfile)
            logger.info(f"Created default configuration file at {CONFIG_FILE_PATH}")
            return True  # Indicates file was created
        except IOError as e:
            logger.error(f"Could not write default config file: {e}", exc_info=True)
            return False
    return False  # File already existed


def load_config() -> None:
    """Loads configuration from file, falling back to defaults."""
    global config_parser  # Use the module-level parser

    # Ensure USER_CONFIG_DIR exists before trying to read/write config
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(
            f"Could not create config directory {USER_CONFIG_DIR}: {e}", exc_info=True
        )
        # In this critical case, we might have to rely on hardcoded defaults entirely
        # or exit. For now, it will try to proceed but likely fail to save.

    create_default_config_file()  # Create if it doesn't exist

    try:
        if CONFIG_FILE_PATH.exists():
            config_parser.read(CONFIG_FILE_PATH, encoding="utf-8")
        else:  # Should have been created, but as a fallback, load defaults into parser
            for section, options in DEFAULT_CONFIG.items():
                if section not in config_parser:
                    config_parser.add_section(section)
                for key, value in options.items():
                    config_parser.set(section, key, str(value))

    except configparser.Error as e:
        logger.error(
            f"Could not parse config file {CONFIG_FILE_PATH}: {e}. Using defaults.",
            exc_info=True,
        )
        # Re-initialize parser with defaults if parsing failed
        config_parser = configparser.ConfigParser()  # Reset
        for section, options in DEFAULT_CONFIG.items():
            if section not in config_parser:
                config_parser.add_section(section)
            for key, value in options.items():
                config_parser.set(section, key, str(value))


# --- Accessor Functions for Configuration Values ---
# These functions will get values from the loaded config_parser,
# or return a hardcoded default if the section/key is missing (robustness).


def get_streamlink_quality() -> str:
    """Get the configured streamlink quality setting."""
    return config_parser.get(
        "Streamlink", "quality", fallback=DEFAULT_CONFIG["Streamlink"]["quality"]
    )


def get_streamlink_timeout_liveness() -> int:
    """Get the timeout for liveness checks in seconds."""
    return config_parser.getint(
        "Streamlink",
        "timeout_liveness",
        fallback=int(DEFAULT_CONFIG["Streamlink"]["timeout_liveness"]),
    )


def get_streamlink_timeout_metadata() -> int:
    """Get the timeout for metadata fetching in seconds."""
    return config_parser.getint(
        "Streamlink",
        "timeout_metadata",
        fallback=int(DEFAULT_CONFIG["Streamlink"]["timeout_metadata"]),
    )


def get_max_workers_liveness() -> int:
    """Get the maximum number of workers for liveness checks."""
    return config_parser.getint(
        "Streamlink",
        "max_workers_liveness",
        fallback=int(DEFAULT_CONFIG["Streamlink"]["max_workers_liveness"]),
    )


def get_max_workers_metadata() -> int:
    """Get the maximum number of workers for metadata fetching."""
    return config_parser.getint(
        "Streamlink",
        "max_workers_metadata",
        fallback=int(DEFAULT_CONFIG["Streamlink"]["max_workers_metadata"]),
    )


def get_twitch_disable_ads() -> bool:
    """Get whether Twitch ads should be disabled."""
    return config_parser.getboolean(
        "Streamlink",
        "twitch_disable_ads",
        fallback=DEFAULT_CONFIG["Streamlink"]["twitch_disable_ads"].lower() == "true",
    )


def get_streamlink_player() -> str:
    """Get the configured media player."""
    return config_parser.get(
        "Streamlink", "player", fallback=DEFAULT_CONFIG["Streamlink"]["player"]
    )


# --- Resilience Configuration Accessors ---


def get_retry_max_attempts() -> int:
    """Get the maximum number of retry attempts."""
    return config_parser.getint(
        "Resilience",
        "retry_max_attempts",
        fallback=int(DEFAULT_CONFIG["Resilience"]["retry_max_attempts"]),
    )


def get_retry_base_delay() -> float:
    """Get the base delay for retry attempts in seconds."""
    return config_parser.getfloat(
        "Resilience",
        "retry_base_delay",
        fallback=float(DEFAULT_CONFIG["Resilience"]["retry_base_delay"]),
    )


def get_retry_max_delay() -> float:
    """Get the maximum delay for retry attempts in seconds."""
    return config_parser.getfloat(
        "Resilience",
        "retry_max_delay",
        fallback=float(DEFAULT_CONFIG["Resilience"]["retry_max_delay"]),
    )


def get_retry_exponential_base() -> float:
    """Get the exponential base for backoff calculation."""
    return config_parser.getfloat(
        "Resilience",
        "retry_exponential_base",
        fallback=float(DEFAULT_CONFIG["Resilience"]["retry_exponential_base"]),
    )


def get_retry_jitter() -> bool:
    """Get whether to add jitter to retry delays."""
    return config_parser.getboolean(
        "Resilience",
        "retry_jitter",
        fallback=DEFAULT_CONFIG["Resilience"]["retry_jitter"].lower() == "true",
    )


def get_circuit_breaker_failure_threshold() -> int:
    """Get the failure threshold for circuit breaker."""
    return config_parser.getint(
        "Resilience",
        "circuit_breaker_failure_threshold",
        fallback=int(DEFAULT_CONFIG["Resilience"]["circuit_breaker_failure_threshold"]),
    )


def get_circuit_breaker_recovery_timeout() -> float:
    """Get the recovery timeout for circuit breaker in seconds."""
    return config_parser.getfloat(
        "Resilience",
        "circuit_breaker_recovery_timeout",
        fallback=float(
            DEFAULT_CONFIG["Resilience"]["circuit_breaker_recovery_timeout"]
        ),
    )


def get_circuit_breaker_success_threshold() -> int:
    """Get the success threshold for circuit breaker recovery."""
    return config_parser.getint(
        "Resilience",
        "circuit_breaker_success_threshold",
        fallback=int(DEFAULT_CONFIG["Resilience"]["circuit_breaker_success_threshold"]),
    )


def get_circuit_breaker_enabled() -> bool:
    """Get whether circuit breaker pattern is enabled."""
    return config_parser.getboolean(
        "Resilience",
        "circuit_breaker_enabled",
        fallback=DEFAULT_CONFIG["Resilience"]["circuit_breaker_enabled"].lower()
        == "true",
    )


def get_donation_link() -> str:
    """Get the donation link URL."""
    return config_parser.get(
        "Misc", "donation_link", fallback=DEFAULT_CONFIG["Misc"]["donation_link"]
    )


def is_first_run_completed() -> bool:
    """Check if the first run experience has been completed."""
    return config_parser.getboolean(
        "Misc",
        "first_run_completed",
        fallback=DEFAULT_CONFIG["Misc"]["first_run_completed"].lower() == "true",
    )


def mark_first_run_completed() -> None:
    """Marks that the first run experience has been completed."""
    if "Misc" not in config_parser:
        config_parser.add_section("Misc")
    config_parser.set("Misc", "first_run_completed", "true")
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as configfile:
            config_parser.write(configfile)
        logger.info("Marked first run as completed in config file.")
    except IOError as e:
        logger.error(f"Could not update config file for first_run: {e}", exc_info=True)


def get_last_played_url() -> str:
    """Get the last played stream URL."""
    return config_parser.get("Misc", "last_played_url", fallback="")


def set_last_played_url(url: Optional[str]) -> None:
    """Set the last played stream URL."""
    if "Misc" not in config_parser:
        config_parser.add_section("Misc")
    config_parser.set(
        "Misc", "last_played_url", url if url else ""
    )  # Store empty if None
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as configfile:
            config_parser.write(configfile)
        logger = logging.getLogger(APP_NAME + ".config")  # Get logger here
        logger.debug(f"Saved last_played_url: {url}")
    except IOError as e:
        logger = logging.getLogger(APP_NAME + ".config")
        logger.error(f"Could not update config file for last_played_url: {e}")


# --- Cache Configuration Accessor Functions ---
def get_cache_enabled() -> bool:
    """Get whether caching is enabled."""
    return config_parser.getboolean(
        "Cache", "enabled", fallback=DEFAULT_CONFIG["Cache"]["enabled"] == "true"
    )


def get_cache_ttl_seconds() -> int:
    """Get the cache TTL in seconds."""
    return config_parser.getint(
        "Cache", "ttl_seconds", fallback=int(DEFAULT_CONFIG["Cache"]["ttl_seconds"])
    )


def get_cache_auto_cleanup() -> bool:
    """Get whether automatic cache cleanup is enabled."""
    return config_parser.getboolean(
        "Cache",
        "auto_cleanup",
        fallback=DEFAULT_CONFIG["Cache"]["auto_cleanup"] == "true",
    )


def get_cache_cleanup_interval() -> int:
    """Get the cache cleanup interval in seconds."""
    return config_parser.getint(
        "Cache",
        "cleanup_interval",
        fallback=int(DEFAULT_CONFIG["Cache"]["cleanup_interval"]),
    )


# --- Rate Limiting Configuration Accessor Functions ---
def get_rate_limit_enabled() -> bool:
    """Get whether rate limiting is enabled."""
    return config_parser.getboolean(
        "RateLimit",
        "enabled",
        fallback=DEFAULT_CONFIG["RateLimit"]["enabled"] == "true",
    )


def get_rate_limit_global_requests_per_second() -> float:
    """Get the global rate limit in requests per second."""
    return config_parser.getfloat(
        "RateLimit",
        "global_requests_per_second",
        fallback=float(DEFAULT_CONFIG["RateLimit"]["global_requests_per_second"]),
    )


def get_rate_limit_global_burst_capacity() -> int:
    """Get the global burst capacity."""
    return config_parser.getint(
        "RateLimit",
        "global_burst_capacity",
        fallback=int(DEFAULT_CONFIG["RateLimit"]["global_burst_capacity"]),
    )


def get_rate_limit_platform_configs() -> Dict[str, Dict[str, float]]:
    """Get platform-specific rate limit configurations."""
    platforms = ["twitch", "youtube", "kick", "default"]
    configs = {}

    for platform in platforms:
        rps_key = f"{platform}_requests_per_second"
        burst_key = f"{platform}_burst_capacity"

        configs[platform] = {
            "requests_per_second": config_parser.getfloat(
                "RateLimit",
                rps_key,
                fallback=float(DEFAULT_CONFIG["RateLimit"][rps_key]),
            ),
            "burst_capacity": config_parser.getint(
                "RateLimit",
                burst_key,
                fallback=int(DEFAULT_CONFIG["RateLimit"][burst_key]),
            ),
        }

    return configs


# --- NEW Accessor Functions for Hooks ---
def get_pre_playback_hook() -> str:
    """Get the pre-playback hook script path."""
    return config_parser.get("Misc", "pre_playback_hook", fallback="")


def get_post_playback_hook() -> str:
    """Get the post-playback hook script path."""
    return config_parser.get("Misc", "post_playback_hook", fallback="")


# --- Pagination and UI Configuration ---


def get_streams_per_page() -> int:
    """Get the number of streams to display per page."""
    return config_parser.getint("Interface", "streams_per_page", fallback=20)


def get_enable_search() -> bool:
    """Get whether search functionality is enabled."""
    return config_parser.getboolean("Interface", "enable_search", fallback=True)


def get_enable_category_filter() -> bool:
    """Get whether category filtering is enabled."""
    return config_parser.getboolean(
        "Interface", "enable_category_filter", fallback=True
    )


def get_enable_platform_filter() -> bool:
    """Get whether platform filtering is enabled."""
    return config_parser.getboolean(
        "Interface", "enable_platform_filter", fallback=True
    )


def get_refresh_interval() -> float:
    """Get the UI refresh interval in seconds."""
    return config_parser.getfloat("Interface", "refresh_interval", fallback=2.0)


def get_show_offline_streams() -> bool:
    """Get whether to show offline streams in UI."""
    return config_parser.getboolean("Interface", "show_offline_streams", fallback=False)


# --- Memory Optimization Configuration ---


def get_metadata_cache_size() -> int:
    """Get the maximum number of cached stream metadata entries."""
    return config_parser.getint("Memory", "metadata_cache_size", fallback=100)


def get_lazy_load_threshold() -> int:
    """Get the stream count threshold for enabling lazy loading."""
    return config_parser.getint("Memory", "lazy_load_threshold", fallback=50)


# --- Load config when module is imported ---
load_config()

# --- OLD Constants (to be removed or made to use the getters above) ---
# STREAMLINK_TIMEOUT = 10 (replace with get_streamlink_timeout_liveness/metadata)
# MAX_WORKERS = 4 (replace with get_max_workers_liveness/metadata)
# STREAM_QUALITY = "best" (replace with get_streamlink_quality)
# TWITCH_DISABLE_ADS = True (replace with get_twitch_disable_ads)
# DONATION_LINK = "..." (replace with get_donation_link)
