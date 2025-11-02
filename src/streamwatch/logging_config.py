"""
Enhanced logging configuration for StreamWatch.

Provides structured, configurable logging with proper formatting,
rotation, and performance considerations.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from . import config
from .constants import LoggingConstants


class StreamWatchFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional colors."""
        if hasattr(self, "use_colors") and self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


def setup_logging(
    log_level: str = LoggingConstants.DEFAULT_LOG_LEVEL,
    log_file: Optional[Path] = None,
    enable_console: bool = True,
    enable_colors: bool = True,
) -> None:
    """
    Setup comprehensive logging configuration.

    Args:
        log_level: Default log level
        log_file: Path to log file (None for default)
        enable_console: Whether to enable console logging
        enable_colors: Whether to use colors in console output
    """
    # Get root logger
    root_logger = logging.getLogger()

    # Clear existing handlers
    root_logger.handlers.clear()

    # Set root level
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # File handler
    if log_file is None:
        log_dir = config.USER_CONFIG_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "streamwatch.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=LoggingConstants.MAX_LOG_SIZE,
        backupCount=LoggingConstants.BACKUP_COUNT,
        encoding="utf-8",
    )

    file_formatter = StreamWatchFormatter(LoggingConstants.FILE_LOG_FORMAT)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(getattr(logging, LoggingConstants.FILE_LOG_LEVEL))
    root_logger.addHandler(file_handler)

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = StreamWatchFormatter(LoggingConstants.CONSOLE_LOG_FORMAT)
        console_formatter.use_colors = enable_colors and sys.stdout.isatty()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(getattr(logging, LoggingConstants.CONSOLE_LOG_LEVEL))
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


def set_module_log_level(module_name: str, level: str) -> None:
    """Set log level for a specific module."""
    logger = logging.getLogger(module_name)
    logger.setLevel(getattr(logging, level.upper()))


# Performance logging utilities
class PerformanceLogger:
    """Logger for performance metrics."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(f"{config.APP_NAME}.perf.{name}")

    def log_duration(self, operation: str, duration: float, **kwargs) -> None:
        """Log operation duration."""
        extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info(f"{operation} took {duration:.3f}s {extra_info}")

    def log_count(self, operation: str, count: int, **kwargs) -> None:
        """Log operation count."""
        extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info(f"{operation} processed {count} items {extra_info}")


# Security logging utilities
class SecurityLogger:
    """Logger for security events."""

    def __init__(self):
        self.logger = logging.getLogger(f"{config.APP_NAME}.security")

    def log_validation_failure(self, field: str, value: str, reason: str) -> None:
        """Log validation failure."""
        # Sanitize value for logging
        safe_value = value[:50] + "..." if len(value) > 50 else value
        self.logger.warning(
            f"Validation failed for {field}: {reason} (value: {safe_value})"
        )

    def log_rate_limit_exceeded(self, identifier: str, limit: float) -> None:
        """Log rate limit exceeded."""
        self.logger.warning(f"Rate limit exceeded for {identifier} (limit: {limit})")

    def log_suspicious_activity(self, activity: str, details: str) -> None:
        """Log suspicious activity."""
        self.logger.error(f"Suspicious activity detected: {activity} - {details}")
