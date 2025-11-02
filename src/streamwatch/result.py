"""
Result pattern implementation for standardized error handling.

This module provides a Result type that encapsulates success/failure states,
eliminating the need for mixed exception/return code patterns.
"""

from typing import Any, Callable, Generic, Optional, TypeVar, Union

T = TypeVar("T")  # Success type
E = TypeVar("E")  # Error type


class Result(Generic[T, E]):
    """
    A Result type that represents either success (Ok) or failure (Err).

    This eliminates the need for mixed exception/return code patterns
    and provides a consistent way to handle operations that can fail.
    """

    def __init__(
        self, value: Optional[T] = None, error: Optional[E] = None, is_ok: bool = True
    ):
        """
        Initialize Result. Use Ok() or Err() class methods instead.

        Args:
            value: Success value
            error: Error value
            is_ok: Whether this represents success
        """
        self._value = value
        self._error = error
        self._is_ok = is_ok

    @classmethod
    def Ok(cls, value: T) -> "Result[T, E]":
        """Create a successful Result."""
        return cls(value=value, is_ok=True)

    @classmethod
    def Err(cls, error: E) -> "Result[T, E]":
        """Create a failed Result."""
        return cls(error=error, is_ok=False)

    def is_ok(self) -> bool:
        """Check if Result represents success."""
        return self._is_ok

    def is_err(self) -> bool:
        """Check if Result represents failure."""
        return not self._is_ok

    def unwrap(self) -> T:
        """
        Get the success value, raising an exception if this is an error.

        Returns:
            The success value

        Raises:
            ValueError: If this Result represents an error
        """
        if self._is_ok:
            return self._value
        raise ValueError(f"Called unwrap() on an Err Result: {self._error}")

    def unwrap_or(self, default: T) -> T:
        """
        Get the success value or return a default if this is an error.

        Args:
            default: Default value to return on error

        Returns:
            Success value or default
        """
        return self._value if self._is_ok else default

    def unwrap_err(self) -> E:
        """
        Get the error value, raising an exception if this is success.

        Returns:
            The error value

        Raises:
            ValueError: If this Result represents success
        """
        if not self._is_ok:
            return self._error
        raise ValueError(f"Called unwrap_err() on an Ok Result: {self._value}")

    def map(self, func: Callable[[T], Any]) -> "Result[Any, E]":
        """
        Apply a function to the success value if Ok, otherwise return the error.

        Args:
            func: Function to apply to success value

        Returns:
            New Result with transformed success value or original error
        """
        if self._is_ok:
            try:
                return Result.Ok(func(self._value))
            except Exception as e:
                return Result.Err(e)
        return Result.Err(self._error)

    def map_err(self, func: Callable[[E], Any]) -> "Result[T, Any]":
        """
        Apply a function to the error value if Err, otherwise return the success.

        Args:
            func: Function to apply to error value

        Returns:
            New Result with transformed error value or original success
        """
        if not self._is_ok:
            return Result.Err(func(self._error))
        return Result.Ok(self._value)

    def and_then(self, func: Callable[[T], "Result[Any, E]"]) -> "Result[Any, E]":
        """
        Chain operations that return Results (flatMap/bind operation).

        Args:
            func: Function that takes success value and returns a Result

        Returns:
            Result from func if Ok, otherwise original error
        """
        if self._is_ok:
            return func(self._value)
        return Result.Err(self._error)

    def or_else(self, func: Callable[[E], "Result[T, Any]"]) -> "Result[T, Any]":
        """
        Provide an alternative Result if this one is an error.

        Args:
            func: Function that takes error value and returns a Result

        Returns:
            Original Result if Ok, otherwise result from func
        """
        if self._is_ok:
            return Result.Ok(self._value)
        return func(self._error)

    def __str__(self) -> str:
        """String representation of Result."""
        if self._is_ok:
            return f"Ok({self._value})"
        return f"Err({self._error})"

    def __repr__(self) -> str:
        """Detailed string representation of Result."""
        return self.__str__()

    def __eq__(self, other) -> bool:
        """Check equality with another Result."""
        if not isinstance(other, Result):
            return False
        return (
            self._is_ok == other._is_ok
            and self._value == other._value
            and self._error == other._error
        )


# Convenience type aliases
StreamResult = Result[Any, str]  # For stream operations
DatabaseResult = Result[Any, str]  # For database operations
ValidationResult = Result[Any, str]  # For validation operations


def safe_call(func: Callable[..., T], *args, **kwargs) -> Result[T, Exception]:
    """
    Safely call a function and return a Result.

    Args:
        func: Function to call
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Result containing return value or exception
    """
    try:
        return Result.Ok(func(*args, **kwargs))
    except Exception as e:
        return Result.Err(e)


def collect_results(results: list[Result[T, E]]) -> Result[list[T], list[E]]:
    """
    Collect a list of Results into a single Result.

    Args:
        results: List of Result objects

    Returns:
        Ok with list of all success values, or Err with list of all errors
    """
    successes = []
    errors = []

    for result in results:
        if result.is_ok():
            successes.append(result.unwrap())
        else:
            errors.append(result.unwrap_err())

    if errors:
        return Result.Err(errors)
    return Result.Ok(successes)
