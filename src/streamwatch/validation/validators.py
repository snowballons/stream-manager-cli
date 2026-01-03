"""
Input validation and security utilities for StreamWatch.

This module provides comprehensive validation and sanitization for all user inputs,
protecting against malicious data and ensuring data integrity throughout the application.
"""

import html
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import validators

from .. import config
from ..core.constants import SecurityConstants, ValidationLimits

logger = logging.getLogger(config.APP_NAME + ".validators")

# Compile regex patterns for better performance
ALIAS_ALLOWED_CHARS = re.compile(SecurityConstants.ALIAS_PATTERN)
USERNAME_ALLOWED_CHARS = re.compile(SecurityConstants.USERNAME_PATTERN)
CATEGORY_ALLOWED_CHARS = re.compile(SecurityConstants.CATEGORY_PATTERN)
CONFIG_KEY_ALLOWED_CHARS = re.compile(SecurityConstants.CONFIG_KEY_PATTERN)

# Known streaming platforms and their URL patterns
SUPPORTED_PLATFORMS: Dict[str, Dict[str, Any]] = {
    "twitch": {
        "domains": ["twitch.tv", "www.twitch.tv", "m.twitch.tv"],
        "patterns": [
            r"^https?://(www\.)?twitch\.tv/([a-zA-Z0-9_]{4,25})/?$",
            r"^https?://m\.twitch\.tv/([a-zA-Z0-9_]{4,25})/?$",
        ],
        "username_group": 2,
    },
    "youtube": {
        "domains": ["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"],
        "patterns": [
            r"^https?://(www\.)?youtube\.com/(@[a-zA-Z0-9_\-]{1,30}|c/[a-zA-Z0-9_\-]{1,100}|channel/[a-zA-Z0-9_\-]{24}|user/[a-zA-Z0-9_\-]{1,20})/?$",
            r"^https?://m\.youtube\.com/(@[a-zA-Z0-9_\-]{1,30}|c/[a-zA-Z0-9_\-]{1,100}|channel/[a-zA-Z0-9_\-]{24}|user/[a-zA-Z0-9_\-]{1,20})/?$",
            r"^https?://youtu\.be/([a-zA-Z0-9_\-]{11})/?$",
        ],
        "username_group": 2,
    },
    "kick": {
        "domains": ["kick.com", "www.kick.com"],
        "patterns": [r"^https?://(www\.)?kick\.com/([a-zA-Z0-9_\-]{1,25})/?$"],
        "username_group": 2,
    },
}

# Dangerous patterns to block (from constants)
DANGEROUS_PATTERNS = SecurityConstants.DANGEROUS_PATTERNS


class ValidationError(Exception):
    """Exception raised when validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value
        self.message = message


class SecurityError(ValidationError):
    """Exception raised when security validation fails."""

    pass


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.

    Args:
        text: Input text that may contain HTML

    Returns:
        HTML-escaped text safe for display
    """
    if not isinstance(text, str):
        text = str(text)

    # HTML escape
    sanitized = html.escape(text, quote=True)

    # Additional security: remove any remaining dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

    return sanitized


def validate_url(url: str, strict: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate and analyze a streaming URL.

    Args:
        url: URL to validate
        strict: If True, only allow known streaming platforms

    Returns:
        Tuple of (is_valid, sanitized_url, metadata)
        metadata contains: platform, username, domain, etc.
    """
    if not isinstance(url, str):
        raise ValidationError("URL must be a string", "url", url)

    # Basic length check
    if len(url) > ValidationLimits.MAX_URL_LENGTH:
        raise ValidationError(
            f"URL too long (max {ValidationLimits.MAX_URL_LENGTH} characters)",
            "url",
            url,
        )

    if len(url) < ValidationLimits.MIN_URL_LENGTH:
        raise ValidationError(
            f"URL too short (min {ValidationLimits.MIN_URL_LENGTH} characters)",
            "url",
            url,
        )

    # Check for dangerous patterns
    url_lower = url.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, url_lower):
            raise SecurityError(
                f"URL contains dangerous pattern: {pattern}", "url", url
            )

    # Sanitize URL
    try:
        # Parse and reconstruct URL to normalize it
        parsed = urllib.parse.urlparse(url.strip())

        # Ensure scheme is http or https
        if parsed.scheme not in ("http", "https"):
            if not parsed.scheme and (url.startswith("www.") or "." in url):
                # Add https:// if missing
                url = "https://" + url
                parsed = urllib.parse.urlparse(url)
            else:
                raise ValidationError("URL must use HTTP or HTTPS protocol", "url", url)

        # Reconstruct clean URL
        sanitized_url = urllib.parse.urlunparse(parsed)

    except Exception as e:
        raise ValidationError(f"Invalid URL format: {e}", "url", url)

    # Validate URL format
    if not validators.url(sanitized_url):
        raise ValidationError("Invalid URL format", "url", sanitized_url)

    # Extract metadata
    metadata = {
        "platform": "Unknown",
        "username": "unknown_stream",
        "domain": parsed.netloc.lower(),
        "path": parsed.path,
        "original_url": url,
        "sanitized_url": sanitized_url,
    }

    # Check against known platforms
    platform_found = False
    for platform_name, platform_info in SUPPORTED_PLATFORMS.items():
        # Check domain
        if metadata["domain"] in platform_info["domains"]:
            # Check URL pattern
            for pattern in platform_info["patterns"]:
                match = re.match(pattern, sanitized_url, re.IGNORECASE)
                if match:
                    # Use proper platform names
                    platform_names = {
                        "youtube": "YouTube",
                        "twitch": "Twitch",
                        "kick": "Kick",
                    }
                    metadata["platform"] = platform_names.get(
                        platform_name, platform_name.title()
                    )

                    # Extract username if pattern has a group
                    username_group = platform_info["username_group"]
                    if len(match.groups()) >= username_group:
                        username = match.group(username_group)
                        # Clean username (remove @ prefix for YouTube)
                        if username.startswith("@"):
                            username = username[1:]
                        metadata["username"] = username

                    platform_found = True
                    break

        if platform_found:
            break

    # If strict mode and platform not found, reject
    if strict and not platform_found:
        raise ValidationError(
            f"Unsupported platform. Supported: {', '.join(SUPPORTED_PLATFORMS.keys())}",
            "url",
            sanitized_url,
        )

    logger.debug(
        f"URL validation successful: {metadata['platform']} - {metadata['username']}"
    )

    return True, sanitized_url, metadata


def validate_alias(alias: str) -> str:
    """
    Validate and sanitize stream alias.

    Args:
        alias: Stream alias to validate

    Returns:
        Sanitized alias
    """
    if not isinstance(alias, str):
        raise ValidationError("Alias must be a string", "alias", alias)

    # Strip whitespace
    alias = alias.strip()

    # Check length
    if len(alias) < ValidationLimits.MIN_ALIAS_LENGTH:
        raise ValidationError("Alias cannot be empty", "alias", alias)

    if len(alias) > ValidationLimits.MAX_ALIAS_LENGTH:
        raise ValidationError(
            f"Alias too long (max {ValidationLimits.MAX_ALIAS_LENGTH} characters)",
            "alias",
            alias,
        )

    # Check for dangerous patterns
    alias_lower = alias.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, alias_lower):
            raise SecurityError(
                f"Alias contains dangerous pattern: {pattern}", "alias", alias
            )

    # Check allowed characters
    if not ALIAS_ALLOWED_CHARS.match(alias):
        raise ValidationError(
            "Alias contains invalid characters. Allowed: letters, numbers, spaces, hyphens, underscores, dots, parentheses, brackets",
            "alias",
            alias,
        )

    # Sanitize HTML
    sanitized = sanitize_html(alias)

    logger.debug(f"Alias validation successful: '{sanitized}'")

    return sanitized


def validate_username(username: str) -> str:
    """
    Validate and sanitize username.

    Args:
        username: Username to validate

    Returns:
        Sanitized username
    """
    if not isinstance(username, str):
        raise ValidationError("Username must be a string", "username", username)

    # Strip whitespace and @ symbols
    username = username.strip().lstrip("@")

    # Check length
    if not username:
        raise ValidationError("Username cannot be empty", "username", username)

    if len(username) > ValidationLimits.MAX_USERNAME_LENGTH:
        raise ValidationError(
            f"Username too long (max {ValidationLimits.MAX_USERNAME_LENGTH} characters)",
            "username",
            username,
        )

    # Check for dangerous patterns
    username_lower = username.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, username_lower):
            raise SecurityError(
                f"Username contains dangerous pattern: {pattern}", "username", username
            )

    # Check allowed characters (more restrictive than alias)
    if not USERNAME_ALLOWED_CHARS.match(username):
        raise ValidationError(
            "Username contains invalid characters. Allowed: letters, numbers, hyphens, underscores, dots",
            "username",
            username,
        )

    # Sanitize HTML
    sanitized = sanitize_html(username)

    logger.debug(f"Username validation successful: '{sanitized}'")

    return sanitized


def validate_category(category: str) -> str:
    """
    Validate and sanitize category.

    Args:
        category: Category to validate

    Returns:
        Sanitized category
    """
    if not isinstance(category, str):
        category = str(category) if category is not None else "N/A"

    # Strip whitespace
    category = category.strip()

    # Default if empty
    if not category:
        return "N/A"

    # Check length
    if len(category) > ValidationLimits.MAX_CATEGORY_LENGTH:
        raise ValidationError(
            f"Category too long (max {ValidationLimits.MAX_CATEGORY_LENGTH} characters)",
            "category",
            category,
        )

    # Check for dangerous patterns
    category_lower = category.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, category_lower):
            raise SecurityError(
                f"Category contains dangerous pattern: {pattern}", "category", category
            )

    # Check allowed characters
    if not CATEGORY_ALLOWED_CHARS.match(category):
        raise ValidationError(
            "Category contains invalid characters. Allowed: letters, numbers, spaces, hyphens, underscores, dots, parentheses, brackets, ampersands",
            "category",
            category,
        )

    # Sanitize HTML
    sanitized = sanitize_html(category)

    logger.debug(f"Category validation successful: '{sanitized}'")

    return sanitized


def validate_title(title: str) -> str:
    """
    Validate and sanitize stream title.

    Args:
        title: Stream title to validate

    Returns:
        Sanitized title
    """
    if not isinstance(title, str):
        title = str(title) if title is not None else ""

    # Strip whitespace
    title = title.strip()

    # Allow empty titles
    if not title:
        return ""

    # Check length
    if len(title) > ValidationLimits.MAX_TITLE_LENGTH:
        raise ValidationError(
            f"Title too long (max {ValidationLimits.MAX_TITLE_LENGTH} characters)",
            "title",
            title,
        )

    # Check for dangerous patterns
    title_lower = title.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, title_lower):
            raise SecurityError(
                f"Title contains dangerous pattern: {pattern}", "title", title
            )

    # Sanitize HTML
    sanitized = sanitize_html(title)

    logger.debug(
        f"Title validation successful: '{sanitized[:50]}{'...' if len(sanitized) > 50 else ''}'"
    )

    return sanitized


def validate_file_path(
    file_path: Union[str, Path],
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
) -> Path:
    """
    Validate and sanitize file path.

    Args:
        file_path: File path to validate
        must_exist: If True, path must exist
        must_be_file: If True, path must be a file
        must_be_dir: If True, path must be a directory

    Returns:
        Sanitized Path object
    """
    if not isinstance(file_path, (str, Path)):
        raise ValidationError(
            "File path must be a string or Path object", "file_path", file_path
        )

    # Convert to string for validation
    path_str = str(file_path).strip()

    # Check length
    if len(path_str) > ValidationLimits.MAX_FILE_PATH_LENGTH:
        raise ValidationError(
            f"File path too long (max {ValidationLimits.MAX_FILE_PATH_LENGTH} characters)",
            "file_path",
            path_str,
        )

    # Check for dangerous patterns
    path_lower = path_str.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, path_lower):
            raise SecurityError(
                f"File path contains dangerous pattern: {pattern}",
                "file_path",
                path_str,
            )

    # Check for path traversal attempts
    dangerous_path_patterns = [
        r"\.\.",  # Parent directory traversal
        r"~/",  # Home directory (could be dangerous in some contexts)
        r"/etc/",  # System directories
        r"/proc/",
        r"/sys/",
        r"\\\\",  # UNC paths on Windows
    ]

    for pattern in dangerous_path_patterns:
        if re.search(pattern, path_str):
            raise SecurityError(
                f"File path contains potentially dangerous pattern: {pattern}",
                "file_path",
                path_str,
            )

    try:
        # Create Path object and resolve
        path_obj = Path(path_str).expanduser()

        # Additional security: ensure path is within reasonable bounds
        # Convert to absolute path to check
        abs_path = path_obj.resolve()

        # Check if path exists if required
        if must_exist and not abs_path.exists():
            raise ValidationError(
                f"Path does not exist: {abs_path}", "file_path", path_str
            )

        # Check if path is file if required
        if must_be_file and abs_path.exists() and not abs_path.is_file():
            raise ValidationError(
                f"Path is not a file: {abs_path}", "file_path", path_str
            )

        # Check if path is directory if required
        if must_be_dir and abs_path.exists() and not abs_path.is_dir():
            raise ValidationError(
                f"Path is not a directory: {abs_path}", "file_path", path_str
            )

        logger.debug(f"File path validation successful: '{abs_path}'")

        return abs_path

    except (OSError, ValueError) as e:
        raise ValidationError(f"Invalid file path: {e}", "file_path", path_str)


def validate_viewer_count(viewer_count: Union[int, str, None]) -> Optional[int]:
    """
    Validate and sanitize viewer count.

    Args:
        viewer_count: Viewer count to validate

    Returns:
        Validated viewer count or None
    """
    if viewer_count is None:
        return None

    # Convert to int if string
    if isinstance(viewer_count, str):
        viewer_count = viewer_count.strip()
        if not viewer_count:
            return None

        try:
            viewer_count = int(viewer_count)
        except ValueError:
            raise ValidationError(
                "Viewer count must be a number", "viewer_count", viewer_count
            )

    if not isinstance(viewer_count, int):
        raise ValidationError(
            "Viewer count must be an integer", "viewer_count", viewer_count
        )

    # Check range
    if viewer_count < 0:
        raise ValidationError(
            "Viewer count cannot be negative", "viewer_count", viewer_count
        )

    if viewer_count > 10_000_000:  # Reasonable upper limit
        raise ValidationError(
            "Viewer count too high (max 10,000,000)", "viewer_count", viewer_count
        )

    return viewer_count


def validate_config_key(key: str) -> str:
    """
    Validate configuration key.

    Args:
        key: Configuration key to validate

    Returns:
        Sanitized key
    """
    if not isinstance(key, str):
        raise ValidationError("Config key must be a string", "config_key", key)

    key = key.strip()

    if not key:
        raise ValidationError("Config key cannot be empty", "config_key", key)

    if len(key) > 100:
        raise ValidationError(
            "Config key too long (max 100 characters)", "config_key", key
        )

    # Check for dangerous patterns
    key_lower = key.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, key_lower):
            raise SecurityError(
                f"Config key contains dangerous pattern: {pattern}", "config_key", key
            )

    # Allow only safe characters for config keys
    if not re.match(r"^[a-zA-Z0-9_\.\-]+$", key):
        raise ValidationError(
            "Config key contains invalid characters. Allowed: letters, numbers, underscores, dots, hyphens",
            "config_key",
            key,
        )

    return key


def validate_and_sanitize_stream_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize all stream data fields.

    Args:
        data: Dictionary containing stream data

    Returns:
        Dictionary with validated and sanitized data
    """
    sanitized: Dict[str, Any] = {}

    # Required fields
    if "url" not in data:
        raise ValidationError("URL is required", "url", None)

    if "alias" not in data:
        raise ValidationError("Alias is required", "alias", None)

    # Validate URL
    is_valid, sanitized_url, url_metadata = validate_url(data["url"])
    sanitized["url"] = sanitized_url

    # Use metadata to fill in platform and username if not provided
    sanitized["platform"] = data.get("platform", url_metadata["platform"])
    sanitized["username"] = data.get("username", url_metadata["username"])

    # Validate other fields
    sanitized["alias"] = validate_alias(data["alias"])
    sanitized["username"] = validate_username(sanitized["username"])

    # Optional fields
    if "category" in data:
        sanitized["category"] = validate_category(data["category"])

    if "viewer_count" in data:
        sanitized["viewer_count"] = validate_viewer_count(data["viewer_count"])

    if "title" in data:
        sanitized["title"] = validate_title(data["title"])

    # Copy other safe fields
    safe_fields = ["status", "last_checked", "url_type"]
    for field in safe_fields:
        if field in data:
            sanitized[field] = data[field]

    logger.info(
        f"Stream data validation successful: {sanitized['alias']} ({sanitized['platform']})"
    )

    return sanitized


def is_safe_for_display(text: str) -> bool:
    """
    Check if text is safe for display without additional sanitization.

    Args:
        text: Text to check

    Returns:
        True if text is safe for display
    """
    if not isinstance(text, str):
        return False

    # Check for dangerous patterns
    text_lower = text.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text_lower):
            return False

    # Check for HTML tags
    if "<" in text and ">" in text:
        return False

    return True


def sanitize_for_logging(data: Any, max_length: int = 100) -> str:
    """
    Sanitize data for safe logging.

    Args:
        data: Data to sanitize for logging
        max_length: Maximum length of logged string

    Returns:
        Safe string for logging
    """
    try:
        # Convert to string
        text = str(data)

        # Truncate if too long
        if len(text) > max_length:
            text = text[: max_length - 3] + "..."

        # Remove dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            text = re.sub(pattern, "[FILTERED]", text, flags=re.IGNORECASE)

        # HTML escape
        text = html.escape(text)

        return text

    except Exception:
        return "[SANITIZATION_ERROR]"
