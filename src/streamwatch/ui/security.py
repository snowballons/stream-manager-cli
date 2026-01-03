"""
UI security utilities for StreamWatch.

This module provides security functions specifically for user interface components,
including input sanitization, XSS protection, and safe display formatting.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .. import config
from ..validation.validators import (
    DANGEROUS_PATTERNS,
    SecurityError,
    ValidationError,
    sanitize_for_logging,
    sanitize_html,
)

logger = logging.getLogger(config.APP_NAME + ".ui_security")


class UISecurityError(Exception):
    """Exception raised for UI security violations."""

    pass


def sanitize_user_input(
    user_input: str, field_name: str = "input", max_length: int = 1000
) -> str:
    """
    Sanitize user input from UI components.

    Args:
        user_input: Raw user input
        field_name: Name of the field for logging
        max_length: Maximum allowed length

    Returns:
        Sanitized input safe for processing

    Raises:
        UISecurityError: If input contains dangerous content
    """
    if not isinstance(user_input, str):
        user_input = str(user_input)

    # Log original input (safely)
    logger.debug(f"Sanitizing {field_name}: {sanitize_for_logging(user_input, 50)}")

    # Check length
    if len(user_input) > max_length:
        raise UISecurityError(f"{field_name} too long (max {max_length} characters)")

    # Check for dangerous patterns
    user_input_lower = user_input.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, user_input_lower):
            logger.warning(f"Dangerous pattern detected in {field_name}: {pattern}")
            raise UISecurityError(
                f"{field_name} contains potentially dangerous content"
            )

    # Sanitize HTML
    sanitized = sanitize_html(user_input.strip())

    logger.debug(f"Sanitized {field_name}: {sanitize_for_logging(sanitized, 50)}")

    return sanitized


def safe_format_for_display(
    text: str, max_length: int = 200, truncate_suffix: str = "..."
) -> str:
    """
    Format text safely for display in UI components.

    Args:
        text: Text to format
        max_length: Maximum display length
        truncate_suffix: Suffix to add when truncating

    Returns:
        Safe text for display
    """
    if not isinstance(text, str):
        text = str(text) if text is not None else ""

    # Sanitize HTML
    safe_text = sanitize_html(text)

    # Truncate if necessary
    if len(safe_text) > max_length:
        safe_text = safe_text[: max_length - len(truncate_suffix)] + truncate_suffix

    return safe_text


def safe_format_stream_info(stream_info: Dict[str, Any]) -> Dict[str, str]:
    """
    Format stream information safely for UI display.

    Args:
        stream_info: Dictionary containing stream information

    Returns:
        Dictionary with safely formatted display strings
    """
    safe_info = {}

    # Format each field safely
    safe_info["alias"] = safe_format_for_display(
        stream_info.get("alias", "Unknown Stream"), 50
    )
    safe_info["platform"] = safe_format_for_display(
        stream_info.get("platform", "Unknown"), 20
    )
    safe_info["username"] = safe_format_for_display(
        stream_info.get("username", "unknown"), 30
    )
    safe_info["category"] = safe_format_for_display(
        stream_info.get("category", "N/A"), 30
    )
    safe_info["status"] = safe_format_for_display(
        str(stream_info.get("status", "unknown")), 20
    )

    # Format viewer count
    viewer_count = stream_info.get("viewer_count")
    if viewer_count is not None:
        try:
            count = int(viewer_count)
            if count >= 1000000:
                safe_info["viewer_count"] = f"{count / 1000000:.1f}M"
            elif count >= 1000:
                safe_info["viewer_count"] = f"{count / 1000:.1f}K"
            else:
                safe_info["viewer_count"] = str(count)
        except (ValueError, TypeError):
            safe_info["viewer_count"] = "N/A"
    else:
        safe_info["viewer_count"] = "N/A"

    # Format title if present
    if "title" in stream_info:
        safe_info["title"] = safe_format_for_display(stream_info["title"], 100)

    # Format URL (show domain only for security)
    url = stream_info.get("url", "")
    if url:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            safe_info["domain"] = safe_format_for_display(parsed.netloc, 50)
        except Exception:
            safe_info["domain"] = "Unknown"
    else:
        safe_info["domain"] = "Unknown"

    return safe_info


def validate_ui_command(command: str, allowed_commands: List[str]) -> str:
    """
    Validate UI command input.

    Args:
        command: Command string from UI
        allowed_commands: List of allowed commands

    Returns:
        Validated command

    Raises:
        UISecurityError: If command is not allowed
    """
    if not isinstance(command, str):
        raise UISecurityError("Command must be a string")

    command = command.strip().lower()

    if not command:
        raise UISecurityError("Command cannot be empty")

    # Check against allowed commands
    if command not in [cmd.lower() for cmd in allowed_commands]:
        logger.warning(
            f"Unauthorized command attempted: {sanitize_for_logging(command)}"
        )
        raise UISecurityError(f"Command not allowed: {command}")

    # Additional security check
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            logger.warning(f"Dangerous pattern in command: {pattern}")
            raise UISecurityError("Command contains dangerous content")

    return command


def safe_format_error_message(error: Exception, show_details: bool = False) -> str:
    """
    Format error messages safely for UI display.

    Args:
        error: Exception to format
        show_details: Whether to show detailed error information

    Returns:
        Safe error message for display
    """
    if isinstance(error, (ValidationError, SecurityError, UISecurityError)):
        # These are safe to display as they're our own validation errors
        message = str(error)
    else:
        # Generic errors might contain sensitive information
        if show_details:
            message = str(error)
        else:
            message = "An error occurred. Please check your input and try again."

    # Sanitize the message
    safe_message = safe_format_for_display(message, 200)

    return safe_message


def create_safe_prompt_choices(
    choices: List[str], max_choice_length: int = 50
) -> List[str]:
    """
    Create safe choices for UI prompts.

    Args:
        choices: List of choice strings
        max_choice_length: Maximum length for each choice

    Returns:
        List of sanitized choices
    """
    safe_choices = []

    for choice in choices:
        if not isinstance(choice, str):
            choice = str(choice)

        # Sanitize and format
        safe_choice = safe_format_for_display(choice, max_choice_length)

        # Ensure choice is not empty after sanitization
        if safe_choice.strip():
            safe_choices.append(safe_choice)

    return safe_choices


def log_user_action(
    action: str, details: Optional[Dict[str, Any]] = None, user_id: str = "unknown"
) -> None:
    """
    Safely log user actions for security monitoring.

    Args:
        action: Action performed by user
        details: Additional details about the action
        user_id: User identifier (if available)
    """
    # Sanitize all inputs for logging
    safe_action = sanitize_for_logging(action, 100)
    safe_user_id = sanitize_for_logging(user_id, 50)

    log_message = f"User action: {safe_action} (user: {safe_user_id})"

    if details:
        safe_details = {}
        for key, value in details.items():
            safe_key = sanitize_for_logging(str(key), 50)
            safe_value = sanitize_for_logging(str(value), 100)
            safe_details[safe_key] = safe_value

        log_message += f" Details: {safe_details}"

    logger.info(log_message)


def check_input_rate_limit(
    user_id: str, action: str, max_actions: int = 10, time_window: int = 60
) -> bool:
    """
    Simple rate limiting for user inputs to prevent abuse.

    Args:
        user_id: User identifier
        action: Action being performed
        max_actions: Maximum actions allowed in time window
        time_window: Time window in seconds

    Returns:
        True if action is allowed, False if rate limited
    """
    # This is a simple implementation - in production you might want to use Redis or similar
    import time
    from collections import defaultdict, deque

    # Simple in-memory rate limiting (not persistent across restarts)
    if not hasattr(check_input_rate_limit, "_rate_limits"):
        check_input_rate_limit._rate_limits = defaultdict(lambda: defaultdict(deque))

    current_time = time.time()
    user_actions = check_input_rate_limit._rate_limits[user_id][action]

    # Remove old entries
    while user_actions and user_actions[0] < current_time - time_window:
        user_actions.popleft()

    # Check if limit exceeded
    if len(user_actions) >= max_actions:
        logger.warning(
            f"Rate limit exceeded for user {sanitize_for_logging(user_id)} action {sanitize_for_logging(action)}"
        )
        return False

    # Add current action
    user_actions.append(current_time)
    return True


def sanitize_config_input(key: str, value: Any) -> tuple[str, Any]:
    """
    Sanitize configuration input from UI.

    Args:
        key: Configuration key
        value: Configuration value

    Returns:
        Tuple of (sanitized_key, sanitized_value)

    Raises:
        UISecurityError: If input is dangerous
    """
    # Sanitize key
    if not isinstance(key, str):
        raise UISecurityError("Configuration key must be a string")

    key = key.strip()

    # Check key format
    if not re.match(r"^[a-zA-Z0-9_\.\-]+$", key):
        raise UISecurityError("Configuration key contains invalid characters")

    if len(key) > 100:
        raise UISecurityError("Configuration key too long")

    # Check for dangerous patterns in key
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, key.lower()):
            raise UISecurityError("Configuration key contains dangerous content")

    # Sanitize value based on type
    if isinstance(value, str):
        # String values need HTML sanitization
        if len(value) > 1000:
            raise UISecurityError("Configuration value too long")

        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, value.lower()):
                raise UISecurityError("Configuration value contains dangerous content")

        sanitized_value = sanitize_html(value)

    elif isinstance(value, (int, float, bool)):
        # Numeric and boolean values are safe
        sanitized_value = value

    elif isinstance(value, (list, dict)):
        # Complex types - convert to string and sanitize
        value_str = str(value)
        if len(value_str) > 2000:
            raise UISecurityError("Configuration value too complex")

        sanitized_value = value  # Keep original structure but log it
        logger.info(f"Complex config value set: {sanitize_for_logging(value_str)}")

    else:
        # Unknown type - convert to string and sanitize
        sanitized_value = sanitize_html(str(value))

    return key, sanitized_value
