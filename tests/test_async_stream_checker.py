"""
Tests for async stream checker functionality.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from streamwatch.async_stream_checker import (
    AsyncStreamChecker,
    create_async_stream_checker,
)
from streamwatch.stream_checker import StreamCheckResult, MetadataResult


class TestAsyncStreamChecker:
    """Test cases for AsyncStreamChecker."""

    @pytest.fixture
    def async_checker(self):
        """Create AsyncStreamChecker instance for testing."""
        return create_async_stream_checker(max_concurrent=2)

    @pytest.mark.asyncio
    async def test_check_stream_async_success(self, async_checker):
        """Test successful async stream check."""
        url = "https://example.com/stream"

        with patch.object(async_checker, "_run_streamlink_check_async") as mock_check:
            mock_check.return_value = StreamCheckResult(is_live=True, url=url)

            result = await async_checker.check_stream_async(url)

            assert result.is_ok()
            check_result = result.unwrap()
            assert check_result.is_live
            assert check_result.url == url

    @pytest.mark.asyncio
    async def test_check_multiple_streams_async(self, async_checker):
        """Test checking multiple streams concurrently."""
        urls = [
            "https://example.com/stream1",
            "https://example.com/stream2",
            "https://example.com/stream3",
        ]

        with patch.object(async_checker, "_run_streamlink_check_async") as mock_check:
            # Mock different results for each stream
            mock_check.side_effect = [
                StreamCheckResult(is_live=True, url=urls[0]),
                StreamCheckResult(is_live=False, url=urls[1]),
                StreamCheckResult(is_live=True, url=urls[2]),
            ]

            results = await async_checker.check_multiple_streams_async(urls)

            assert len(results) == 3

            # Check first stream (live)
            url1, result1 = results[0]
            assert url1 == urls[0]
            assert result1.is_ok()
            assert result1.unwrap().is_live

            # Check second stream (not live)
            url2, result2 = results[1]
            assert url2 == urls[1]
            assert result2.is_ok()
            assert not result2.unwrap().is_live

            # Check third stream (live)
            url3, result3 = results[2]
            assert url3 == urls[2]
            assert result3.is_ok()
            assert result3.unwrap().is_live

    @pytest.mark.asyncio
    async def test_fetch_metadata_async_success(self, async_checker):
        """Test successful async metadata fetch."""
        url = "https://example.com/stream"
        json_data = '{"metadata": {"title": "Test Stream"}}'

        with patch.object(
            async_checker, "_run_streamlink_metadata_async"
        ) as mock_fetch:
            mock_fetch.return_value = MetadataResult(
                success=True, url=url, json_data=json_data
            )

            result = await async_checker.fetch_metadata_async(url)

            assert result.is_ok()
            metadata_result = result.unwrap()
            assert metadata_result.success
            assert metadata_result.json_data == json_data

    @pytest.mark.asyncio
    async def test_fetch_live_streams_async_integration(self, async_checker):
        """Test full async live streams fetch integration."""
        stream_data = [
            {
                "url": "https://example.com/stream1",
                "alias": "Stream 1",
                "platform": "Test",
                "username": "user1",
            },
            {
                "url": "https://example.com/stream2",
                "alias": "Stream 2",
                "platform": "Test",
                "username": "user2",
            },
        ]

        # Mock liveness checks
        with patch.object(async_checker, "_run_streamlink_check_async") as mock_check:
            mock_check.side_effect = [
                StreamCheckResult(is_live=True, url=stream_data[0]["url"]),
                StreamCheckResult(is_live=False, url=stream_data[1]["url"]),
            ]

            # Mock metadata fetch for live stream
            with patch.object(
                async_checker, "_run_streamlink_metadata_async"
            ) as mock_metadata:
                mock_metadata.return_value = MetadataResult(
                    success=True,
                    url=stream_data[0]["url"],
                    json_data='{"metadata": {"title": "Live Stream", "viewers": 100}}',
                )

                results = await async_checker.fetch_live_streams_async(stream_data)

                # Should only return the live stream
                assert len(results) == 1

                live_stream = results[0]
                assert live_stream["url"] == stream_data[0]["url"]
                assert live_stream["alias"] == "Stream 1"
                assert live_stream["status"] == "live"

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, async_checker):
        """Test that semaphore properly limits concurrent operations."""
        urls = ["https://example.com/stream{}".format(i) for i in range(5)]

        # Track concurrent calls
        concurrent_calls = 0
        max_concurrent = 0

        async def mock_check_with_tracking(url):
            nonlocal concurrent_calls, max_concurrent
            concurrent_calls += 1
            max_concurrent = max(max_concurrent, concurrent_calls)

            # Simulate some work
            await asyncio.sleep(0.1)

            concurrent_calls -= 1
            return StreamCheckResult(is_live=True, url=url)

        with patch.object(
            async_checker,
            "_run_streamlink_check_async",
            side_effect=mock_check_with_tracking,
        ):
            await async_checker.check_multiple_streams_async(urls)

            # Should not exceed the semaphore limit (2 in this test)
            assert max_concurrent <= 2

    def test_create_async_stream_checker(self):
        """Test factory function for creating async stream checker."""
        checker = create_async_stream_checker(max_concurrent=5)

        assert isinstance(checker, AsyncStreamChecker)
        assert checker.max_concurrent == 5
        assert checker.semaphore._value == 5

    @pytest.mark.asyncio
    async def test_error_handling_in_batch_operations(self, async_checker):
        """Test error handling in batch operations."""
        urls = ["https://example.com/stream1", "https://example.com/stream2"]

        with patch.object(async_checker, "_run_streamlink_check_async") as mock_check:
            # First call succeeds, second raises exception
            mock_check.side_effect = [
                StreamCheckResult(is_live=True, url=urls[0]),
                Exception("Network error"),
            ]

            results = await async_checker.check_multiple_streams_async(urls)

            assert len(results) == 2

            # First result should be successful
            url1, result1 = results[0]
            assert url1 == urls[0]
            assert result1.is_ok()

            # Second result should contain error
            url2, result2 = results[1]
            assert url2 == urls[1]
            assert result2.is_err()
            assert "Network error" in result2.unwrap_err()


@pytest.mark.asyncio
async def test_module_level_async_functions():
    """Test module-level async convenience functions."""
    from streamwatch.async_stream_checker import (
        check_multiple_streams_async,
        fetch_live_streams_async,
    )

    urls = ["https://example.com/stream1", "https://example.com/stream2"]

    with patch(
        "streamwatch.async_stream_checker.AsyncStreamChecker"
    ) as mock_checker_class:
        mock_checker = MagicMock()
        mock_checker_class.return_value = mock_checker

        # Test check_multiple_streams_async
        mock_checker.check_multiple_streams_async = AsyncMock(return_value=[])
        results = await check_multiple_streams_async(urls)

        mock_checker.check_multiple_streams_async.assert_called_once_with(urls)
        assert results == []

        # Test fetch_live_streams_async
        stream_data = [{"url": "https://example.com/stream", "alias": "Test"}]
        mock_checker.fetch_live_streams_async = AsyncMock(return_value=[])
        results = await fetch_live_streams_async(stream_data)

        mock_checker.fetch_live_streams_async.assert_called_once_with(stream_data)
        assert results == []
