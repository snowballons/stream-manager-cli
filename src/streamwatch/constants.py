"""
Application constants and configuration limits.

This module centralizes all magic numbers and configuration limits
to improve maintainability and reduce hardcoded values.
"""


# --- Validation Limits ---
class ValidationLimits:
    """Input validation limits for security and data integrity."""

    # URL validation
    MAX_URL_LENGTH = 2048
    MIN_URL_LENGTH = 10

    # Text field limits
    MAX_ALIAS_LENGTH = 200
    MIN_ALIAS_LENGTH = 1
    MAX_USERNAME_LENGTH = 100
    MIN_USERNAME_LENGTH = 1
    MAX_CATEGORY_LENGTH = 100
    MAX_TITLE_LENGTH = 500
    MAX_FILE_PATH_LENGTH = 1000

    # Numeric limits
    MAX_VIEWER_COUNT = 10_000_000
    MIN_VIEWER_COUNT = 0

    # Configuration limits
    MAX_CONFIG_KEY_LENGTH = 100
    MAX_CONFIG_VALUE_LENGTH = 1000


# --- Performance Limits ---
class PerformanceLimits:
    """Performance-related constants and limits."""

    # Threading limits
    MIN_WORKERS = 1
    MAX_WORKERS_LIVENESS = 50
    MAX_WORKERS_METADATA = 20
    DEFAULT_WORKERS_LIVENESS = 10
    DEFAULT_WORKERS_METADATA = 5

    # Timeout limits (seconds)
    MIN_TIMEOUT = 1
    MAX_TIMEOUT = 120
    DEFAULT_LIVENESS_TIMEOUT = 10
    DEFAULT_METADATA_TIMEOUT = 15

    # Cache limits
    MIN_CACHE_TTL = 60  # 1 minute
    MAX_CACHE_TTL = 3600  # 1 hour
    DEFAULT_CACHE_TTL = 300  # 5 minutes
    MAX_CACHE_SIZE = 1000
    DEFAULT_CACHE_SIZE = 100

    # Rate limiting
    MIN_RATE_LIMIT = 0.1  # requests per second
    MAX_RATE_LIMIT = 100.0
    DEFAULT_RATE_LIMIT = 8.0
    MIN_BURST_CAPACITY = 1
    MAX_BURST_CAPACITY = 100
    DEFAULT_BURST_CAPACITY = 15


# --- Database Constants ---
class DatabaseConstants:
    """Database-related constants."""

    SCHEMA_VERSION = 1
    DEFAULT_DB_NAME = "streamwatch.db"

    # Connection settings
    DEFAULT_TIMEOUT = 30.0
    WAL_MODE = "WAL"
    SYNCHRONOUS_MODE = "NORMAL"
    CACHE_SIZE = -64000  # 64MB

    # Query limits
    MAX_SEARCH_RESULTS = 1000
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


# --- UI Constants ---
class UIConstants:
    """User interface constants."""

    # Pagination
    MIN_STREAMS_PER_PAGE = 5
    MAX_STREAMS_PER_PAGE = 100
    DEFAULT_STREAMS_PER_PAGE = 20

    # Display limits
    MAX_DISPLAY_LENGTH = 200
    TRUNCATE_SUFFIX = "..."

    # Input limits
    MAX_USER_INPUT_LENGTH = 1000

    # Refresh intervals (seconds)
    MIN_REFRESH_INTERVAL = 0.1
    MAX_REFRESH_INTERVAL = 10.0
    DEFAULT_REFRESH_INTERVAL = 2.0


# --- Network Constants ---
class NetworkConstants:
    """Network and streaming constants."""

    # Retry settings
    MIN_RETRY_ATTEMPTS = 1
    MAX_RETRY_ATTEMPTS = 10
    DEFAULT_RETRY_ATTEMPTS = 3

    MIN_RETRY_DELAY = 0.1
    MAX_RETRY_DELAY = 60.0
    DEFAULT_RETRY_DELAY = 1.0

    # Circuit breaker settings
    MIN_FAILURE_THRESHOLD = 1
    MAX_FAILURE_THRESHOLD = 20
    DEFAULT_FAILURE_THRESHOLD = 5

    MIN_RECOVERY_TIMEOUT = 10.0
    MAX_RECOVERY_TIMEOUT = 600.0
    DEFAULT_RECOVERY_TIMEOUT = 60.0


# --- File System Constants ---
class FileSystemConstants:
    """File system and path constants."""

    # Directory names
    CONFIG_DIR_NAME = "streamwatch"
    LOGS_DIR_NAME = "logs"
    CACHE_DIR_NAME = "cache"

    # File names
    CONFIG_FILE_NAME = "config.ini"
    STREAMS_FILE_NAME = "streams.json"
    DATABASE_FILE_NAME = "streamwatch.db"
    LOG_FILE_NAME = "streamwatch.log"

    # File size limits
    MAX_LOG_FILE_SIZE = 1024 * 1024  # 1MB
    MAX_BACKUP_COUNT = 3

    # Recording settings
    DEFAULT_RECORDING_DIR = "StreamWatch"
    MAX_RECORDING_SIZE = 1000  # MB
    DEFAULT_FILENAME_TEMPLATE = "{platform}_{username}_{date}_{time}.{ext}"


# --- Security Constants ---
class SecurityConstants:
    """Security-related constants."""

    # Allowed characters patterns (as strings for re.compile)
    ALIAS_PATTERN = r"^[a-zA-Z0-9\s\-_\.\(\)\[\]]+$"
    USERNAME_PATTERN = r"^[a-zA-Z0-9\-_\.]+$"
    CATEGORY_PATTERN = r"^[a-zA-Z0-9\s\-_\.\(\)\[\]\&/]+$"
    CONFIG_KEY_PATTERN = r"^[a-zA-Z0-9_\.\-]+$"

    # Dangerous patterns to block
    DANGEROUS_PATTERNS = [
        r"javascript:",
        r"data:",
        r"vbscript:",
        r"file:",
        r"ftp:",
        r"<script",
        r"</script>",
        r"<iframe",
        r"</iframe>",
        r"<object",
        r"</object>",
        r"<embed",
        r"</embed>",
        r"onload=",
        r"onerror=",
        r"onclick=",
        r"onmouseover=",
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\.",  # Parent directory traversal
        r"~/",  # Home directory
        r"/etc/",  # System directories
        r"/proc/",
        r"/sys/",
        r"\\\\",  # UNC paths on Windows
    ]


# --- Application Metadata ---
class AppMetadata:
    """Application metadata constants."""

    NAME = "streamwatch"
    VERSION = "0.4.0"
    DESCRIPTION = "A CLI tool to manage, check status, and play favorite live streams."

    # URLs
    HOMEPAGE = "https://snowballons.github.io/streamwatch-cli"
    REPOSITORY = "https://github.com/snowballons/streamwatch-cli"
    DONATION_LINK = "https://buymeacoffee.com/snowballons"

    # Supported platforms
    SUPPORTED_PLATFORMS = [
        "Twitch",
        "YouTube",
        "Kick",
        "TikTok",
        "BiliBili",
        "Douyin",
        "Huya",
        "Vimeo",
        "Dailymotion",
    ]


# --- Quality Settings ---
class QualitySettings:
    """Stream quality constants."""

    DEFAULT_QUALITY = "best"

    # Master fallback order, from best to worst.
    QUALITY_FALLBACK_ORDER = [
        "best",
        "1080p60",
        "1080p",
        "720p60",
        "720p",
        "480p",
        "360p",
        "worst",
    ]

    AVAILABLE_QUALITIES = ["worst", "360p", "480p", "720p", "1080p", "best"]

    DEFAULT_RECORDING_QUALITY = "best"
    DEFAULT_RECORDING_FORMAT = "mp4"


# --- Logging Constants ---
class LoggingConstants:
    """Logging configuration constants."""

    # Log levels
    DEFAULT_LOG_LEVEL = "INFO"
    FILE_LOG_LEVEL = "DEBUG"
    CONSOLE_LOG_LEVEL = "INFO"

    # Log format
    FILE_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
    CONSOLE_LOG_FORMAT = "%(levelname)s: %(message)s"

    # Log rotation
    MAX_LOG_SIZE = 1024 * 1024  # 1MB
    BACKUP_COUNT = 3
