"""
Common validation utilities to reduce code duplication.

This module provides reusable validation patterns and decorators
to eliminate duplicate validation logic across the application.
"""

from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from .constants import ValidationLimits
from .validators import SecurityError, ValidationError

T = TypeVar("T")


def safe_validator(validator_func: Callable[[Any], T]) -> Callable[[Any], T]:
    """
    Decorator to safely wrap validator functions for Pydantic field validators.

    Converts ValidationError and SecurityError to ValueError for Pydantic compatibility.

    Args:
        validator_func: The validator function to wrap

    Returns:
        Wrapped validator function
    """

    @wraps(validator_func)
    def wrapper(value: Any) -> T:
        try:
            return validator_func(value)
        except (ValidationError, SecurityError) as e:
            raise ValueError(str(e))
        except Exception as e:
            raise ValueError(f"Validation failed: {str(e)}")

    return wrapper


def optional_validator(
    validator_func: Callable[[Any], T], default: T = None
) -> Callable[[Optional[Any]], Optional[T]]:
    """
    Create an optional validator that handles None values.

    Args:
        validator_func: The validator function for non-None values
        default: Default value to return for None input

    Returns:
        Optional validator function
    """

    @wraps(validator_func)
    def wrapper(value: Optional[Any]) -> Optional[T]:
        if value is None:
            return default
        return validator_func(value)

    return wrapper


def length_validator(
    min_length: int = 0, max_length: int = None, field_name: str = "field"
) -> Callable[[str], str]:
    """
    Create a length validator for string fields.

    Args:
        min_length: Minimum allowed length
        max_length: Maximum allowed length (None for no limit)
        field_name: Name of field for error messages

    Returns:
        Length validator function
    """

    def validator(value: str) -> str:
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string", field_name, value)

        value = value.strip()

        if len(value) < min_length:
            raise ValidationError(
                f"{field_name} too short (min {min_length} characters)",
                field_name,
                value,
            )

        if max_length is not None and len(value) > max_length:
            raise ValidationError(
                f"{field_name} too long (max {max_length} characters)",
                field_name,
                value,
            )

        return value

    return validator


def range_validator(
    min_value: int = None, max_value: int = None, field_name: str = "field"
) -> Callable[[int], int]:
    """
    Create a range validator for numeric fields.

    Args:
        min_value: Minimum allowed value (None for no limit)
        max_value: Maximum allowed value (None for no limit)
        field_name: Name of field for error messages

    Returns:
        Range validator function
    """

    def validator(value: int) -> int:
        if not isinstance(value, int):
            raise ValidationError(f"{field_name} must be an integer", field_name, value)

        if min_value is not None and value < min_value:
            raise ValidationError(
                f"{field_name} too small (min {min_value})", field_name, value
            )

        if max_value is not None and value > max_value:
            raise ValidationError(
                f"{field_name} too large (max {max_value})", field_name, value
            )

        return value

    return validator


def non_empty_string_validator(field_name: str = "field") -> Callable[[str], str]:
    """
    Create a validator that ensures string is not empty after stripping.

    Args:
        field_name: Name of field for error messages

    Returns:
        Non-empty string validator function
    """

    def validator(value: str) -> str:
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string", field_name, value)

        value = value.strip()

        if not value:
            raise ValidationError(f"{field_name} cannot be empty", field_name, value)

        return value

    return validator


class CommonValidators:
    """
    Collection of commonly used validators with consistent error handling.
    """

    @staticmethod
    @safe_validator
    def url_validator(value: str) -> str:
        """Validate URL using the main validator."""
        from .validators import validate_url

        _, sanitized_url, _ = validate_url(value, strict=False)
        return sanitized_url

    @staticmethod
    @safe_validator
    def alias_validator(value: str) -> str:
        """Validate alias using the main validator."""
        from .validators import validate_alias

        return validate_alias(value)

    @staticmethod
    @safe_validator
    def username_validator(value: str) -> str:
        """Validate username using the main validator."""
        from .validators import validate_username

        return validate_username(value)

    @staticmethod
    @safe_validator
    def category_validator(value: str) -> str:
        """Validate category using the main validator."""
        from .validators import validate_category

        return validate_category(value)

    @staticmethod
    @safe_validator
    def title_validator(value: str) -> str:
        """Validate title using the main validator."""
        from .validators import validate_title

        return validate_title(value)

    @staticmethod
    @safe_validator
    def viewer_count_validator(value: Optional[int]) -> Optional[int]:
        """Validate viewer count using the main validator."""
        from .validators import validate_viewer_count

        return validate_viewer_count(value)

    @staticmethod
    @safe_validator
    def non_negative_int_validator(value: Optional[int]) -> Optional[int]:
        """Validate that integer is non-negative."""
        if value is not None and value < 0:
            raise ValidationError("Value cannot be negative", "value", value)
        return value

    @staticmethod
    @safe_validator
    def quality_validator(value: str) -> str:
        """Validate quality string."""
        validator = non_empty_string_validator("quality")
        return validator(value)

    @staticmethod
    @safe_validator
    def platform_validator(value: str) -> str:
        """Validate and normalize platform name."""
        validator = non_empty_string_validator("platform")
        return validator(value).title()


# Convenience functions for common validation patterns
def create_pydantic_validator(validator_func: Callable[[Any], T]) -> Callable:
    """
    Create a Pydantic field validator from a validation function.

    Args:
        validator_func: The validation function

    Returns:
        Pydantic-compatible field validator
    """

    @safe_validator
    def pydantic_validator(cls, value: Any) -> T:
        return validator_func(value)

    return classmethod(pydantic_validator)


def validators_available_check(
    validator_func: Callable[[Any], T], fallback_func: Callable[[Any], T] = None
) -> Callable[[Any], T]:
    """
    Create a validator that checks if validators module is available.

    Args:
        validator_func: Main validator function
        fallback_func: Fallback validator if main validators not available

    Returns:
        Conditional validator function
    """

    def wrapper(value: Any) -> T:
        try:
            # Try to import validators to check availability
            from . import validators

            return validator_func(value)
        except ImportError:
            if fallback_func:
                return fallback_func(value)
            # Basic fallback - just return the value if it's a string
            if isinstance(value, str):
                return value.strip() if value else value
            return value

    return wrapper
