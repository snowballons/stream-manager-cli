"""Tests for the Result pattern implementation."""

import pytest

from src.streamwatch.result import Result, collect_results, safe_call


class TestResult:
    """Test Result pattern functionality."""

    def test_ok_result(self):
        """Test Ok result creation and methods."""
        result = Result.Ok("success")

        assert result.is_ok()
        assert not result.is_err()
        assert result.unwrap() == "success"
        assert result.unwrap_or("default") == "success"

    def test_err_result(self):
        """Test Err result creation and methods."""
        result = Result.Err("error")

        assert result.is_err()
        assert not result.is_ok()
        assert result.unwrap_err() == "error"
        assert result.unwrap_or("default") == "default"

    def test_unwrap_err_on_ok_raises(self):
        """Test that unwrap_err raises on Ok result."""
        result = Result.Ok("success")

        with pytest.raises(ValueError, match="Called unwrap_err"):
            result.unwrap_err()

    def test_unwrap_on_err_raises(self):
        """Test that unwrap raises on Err result."""
        result = Result.Err("error")

        with pytest.raises(ValueError, match="Called unwrap"):
            result.unwrap()

    def test_map_on_ok(self):
        """Test map operation on Ok result."""
        result = Result.Ok(5)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_ok()
        assert mapped.unwrap() == 10

    def test_map_on_err(self):
        """Test map operation on Err result."""
        result = Result.Err("error")
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_err()
        assert mapped.unwrap_err() == "error"

    def test_and_then_on_ok(self):
        """Test and_then operation on Ok result."""
        result = Result.Ok(5)
        chained = result.and_then(lambda x: Result.Ok(x * 2))

        assert chained.is_ok()
        assert chained.unwrap() == 10

    def test_and_then_on_err(self):
        """Test and_then operation on Err result."""
        result = Result.Err("error")
        chained = result.and_then(lambda x: Result.Ok(x * 2))

        assert chained.is_err()
        assert chained.unwrap_err() == "error"

    def test_or_else_on_ok(self):
        """Test or_else operation on Ok result."""
        result = Result.Ok("success")
        alternative = result.or_else(lambda e: Result.Ok("alternative"))

        assert alternative.is_ok()
        assert alternative.unwrap() == "success"

    def test_or_else_on_err(self):
        """Test or_else operation on Err result."""
        result = Result.Err("error")
        alternative = result.or_else(lambda e: Result.Ok("alternative"))

        assert alternative.is_ok()
        assert alternative.unwrap() == "alternative"

    def test_equality(self):
        """Test Result equality comparison."""
        ok1 = Result.Ok("test")
        ok2 = Result.Ok("test")
        ok3 = Result.Ok("different")
        err1 = Result.Err("error")
        err2 = Result.Err("error")

        assert ok1 == ok2
        assert ok1 != ok3
        assert ok1 != err1
        assert err1 == err2

    def test_string_representation(self):
        """Test Result string representation."""
        ok_result = Result.Ok("success")
        err_result = Result.Err("error")

        assert str(ok_result) == "Ok(success)"
        assert str(err_result) == "Err(error)"


class TestSafeCall:
    """Test safe_call utility function."""

    def test_safe_call_success(self):
        """Test safe_call with successful function."""

        def success_func(x):
            return x * 2

        result = safe_call(success_func, 5)

        assert result.is_ok()
        assert result.unwrap() == 10

    def test_safe_call_exception(self):
        """Test safe_call with function that raises exception."""

        def error_func():
            raise ValueError("test error")

        result = safe_call(error_func)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)
        assert str(result.unwrap_err()) == "test error"


class TestCollectResults:
    """Test collect_results utility function."""

    def test_collect_all_ok(self):
        """Test collect_results with all Ok results."""
        results = [Result.Ok(1), Result.Ok(2), Result.Ok(3)]

        collected = collect_results(results)

        assert collected.is_ok()
        assert collected.unwrap() == [1, 2, 3]

    def test_collect_with_errors(self):
        """Test collect_results with some Err results."""
        results = [
            Result.Ok(1),
            Result.Err("error1"),
            Result.Ok(3),
            Result.Err("error2"),
        ]

        collected = collect_results(results)

        assert collected.is_err()
        assert collected.unwrap_err() == ["error1", "error2"]

    def test_collect_empty_list(self):
        """Test collect_results with empty list."""
        results = []

        collected = collect_results(results)

        assert collected.is_ok()
        assert collected.unwrap() == []
