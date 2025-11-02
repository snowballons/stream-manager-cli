"""
Async Stream Checker for concurrent stream status checking.

This module provides async/await functionality for checking multiple streams
concurrently, significantly improving performance when checking many streams.
"""

import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from . import config
from .cache import get_cache
from .exceptions import (
    NetworkError,
    RateLimitExceededError,
    StreamlinkError,
    StreamNotFoundError,
    TimeoutError,
    categorize_streamlink_error,
)
from .models import StreamInfo, StreamStatus
from .rate_limiter import get_rate_limiter
from .result import Result, StreamResult
from .stream_checker import (
    MetadataResult,
    StreamCheckResult,
    extract_category_keywords,
    sanitize_category_string,
)
from .stream_utils import parse_url_metadata

logger = logging.getLogger(config.APP_NAME + ".async_stream_checker")


class AsyncStreamChecker:
    """Async stream checker for concurrent operations."""

    def __init__(self, max_concurrent: int = None):
        """
        Initialize async stream checker.
        
        Args:
            max_concurrent: Maximum concurrent operations (defaults to config value)
        """
        self.max_concurrent = max_concurrent or config.get_max_workers_liveness()
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.logger = logging.getLogger(config.APP_NAME + ".async_stream_checker")

    async def check_stream_async(self, url: str) -> StreamResult:
        """
        Check single stream asynchronously.
        
        Args:
            url: Stream URL to check
            
        Returns:
            Result containing StreamCheckResult or error
        """
        async with self.semaphore:
            return await self._check_stream_core_async(url)

    async def check_multiple_streams_async(self, urls: List[str]) -> List[Tuple[str, StreamResult]]:
        """
        Check multiple streams concurrently.
        
        Args:
            urls: List of stream URLs to check
            
        Returns:
            List of (url, result) tuples
        """
        if not urls:
            return []

        self.logger.info(f"Checking {len(urls)} streams concurrently...")
        
        # Create tasks for all URLs
        tasks = [self.check_stream_async(url) for url in urls]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                error_result = Result.Err(f"Unexpected error: {str(result)}")
                processed_results.append((url, error_result))
            else:
                processed_results.append((url, result))
        
        return processed_results

    async def fetch_metadata_async(self, url: str) -> StreamResult:
        """
        Fetch stream metadata asynchronously.
        
        Args:
            url: Stream URL to fetch metadata for
            
        Returns:
            Result containing MetadataResult or error
        """
        async with self.semaphore:
            return await self._fetch_metadata_core_async(url)

    async def fetch_multiple_metadata_async(self, urls: List[str]) -> List[Tuple[str, StreamResult]]:
        """
        Fetch metadata for multiple streams concurrently.
        
        Args:
            urls: List of stream URLs
            
        Returns:
            List of (url, result) tuples
        """
        if not urls:
            return []

        self.logger.info(f"Fetching metadata for {len(urls)} streams concurrently...")
        
        # Create tasks for all URLs
        tasks = [self.fetch_metadata_async(url) for url in urls]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                error_result = Result.Err(f"Unexpected error: {str(result)}")
                processed_results.append((url, error_result))
            else:
                processed_results.append((url, result))
        
        return processed_results

    async def fetch_live_streams_async(self, all_configured_streams_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Async version of fetch_live_streams with concurrent processing.
        
        Args:
            all_configured_streams_data: List of configured stream dictionaries
            
        Returns:
            List of live stream info dictionaries
        """
        if not all_configured_streams_data:
            self.logger.info("No configured streams to check.")
            return []

        self.logger.info(f"Checking {len(all_configured_streams_data)} streams for liveness...")
        
        # Phase 1: Concurrent liveness check
        urls = [s["url"] for s in all_configured_streams_data]
        liveness_results = await self.check_multiple_streams_async(urls)
        
        # Filter live streams
        live_urls = []
        for url, result in liveness_results:
            if result.is_ok():
                check_result = result.unwrap()
                if check_result.is_live:
                    live_urls.append(url)
                elif check_result.error:
                    self.logger.debug(f"Stream check failed for {url}: {check_result.error}")
            else:
                self.logger.warning(f"Stream check error for {url}: {result.unwrap_err()}")

        if not live_urls:
            self.logger.info("No streams appear to be live based on initial check.")
            return []

        self.logger.info(f"Found {len(live_urls)} potentially live stream(s).")
        
        # Phase 2: Concurrent metadata fetch
        metadata_results = await self.fetch_multiple_metadata_async(live_urls)
        
        # Create StreamInfo objects
        url_to_details_map = {s["url"]: s for s in all_configured_streams_data}
        live_streams_info = []
        
        for url, result in metadata_results:
            if url not in url_to_details_map:
                continue
                
            stream_data = url_to_details_map[url]
            
            if result.is_ok():
                metadata_result = result.unwrap()
                stream_info = self._create_stream_info_from_metadata(url, metadata_result, stream_data)
            else:
                # Create basic stream info without metadata
                stream_info = StreamInfo(
                    url=url,
                    alias=stream_data.get("alias", "Unnamed"),
                    platform=stream_data.get("platform", "Unknown"),
                    username=stream_data.get("username", "unknown"),
                    category="N/A",
                    status=StreamStatus.LIVE,
                )
            
            if stream_info:
                live_streams_info.append(stream_info)

        return [s.model_dump() for s in live_streams_info]

    async def _check_stream_core_async(self, url: str) -> StreamResult:
        """Core async stream checking logic."""
        if not url or not isinstance(url, str):
            return Result.Err("Invalid URL provided")

        # Check cache first
        if config.get_cache_enabled():
            cache = get_cache()
            cached_status = cache.get(url)
            if cached_status is not None:
                self.logger.debug(f"Using cached status for {url}: {cached_status.value}")
                result = StreamCheckResult(
                    is_live=(cached_status == StreamStatus.LIVE),
                    url=url
                )
                return Result.Ok(result)

        # Apply rate limiting
        if config.get_rate_limit_enabled():
            rate_limiter = get_rate_limiter()
            timeout = config.get_streamlink_timeout_liveness()
            
            if not rate_limiter.acquire(url, timeout=timeout):
                return Result.Err(f"Rate limit exceeded for {url}")

        # Execute streamlink command asynchronously
        try:
            result = await self._run_streamlink_check_async(url)
            
            # Update cache
            if config.get_cache_enabled():
                cache = get_cache()
                status = StreamStatus.LIVE if result.is_live else StreamStatus.OFFLINE
                if result.error and isinstance(result.error, StreamNotFoundError):
                    status = StreamStatus.OFFLINE
                elif result.error:
                    status = StreamStatus.ERROR
                    
                cache.put(url, status)
                self.logger.debug(f"Cached status for {url}: {status.value}")
            
            return Result.Ok(result)
            
        except Exception as e:
            return Result.Err(f"Stream check failed: {str(e)}")

    async def _fetch_metadata_core_async(self, url: str) -> StreamResult:
        """Core async metadata fetching logic."""
        if not url or not isinstance(url, str):
            return Result.Err("Invalid URL provided")

        # Apply rate limiting
        if config.get_rate_limit_enabled():
            rate_limiter = get_rate_limiter()
            timeout = config.get_streamlink_timeout_metadata()
            
            if not rate_limiter.acquire(url, timeout=timeout):
                return Result.Err(f"Rate limit exceeded for {url}")

        # Execute streamlink metadata command asynchronously
        try:
            result = await self._run_streamlink_metadata_async(url)
            return Result.Ok(result)
        except Exception as e:
            return Result.Err(f"Metadata fetch failed: {str(e)}")

    async def _run_streamlink_check_async(self, url: str) -> StreamCheckResult:
        """Run streamlink liveness check asynchronously."""
        command = ["streamlink"]
        if config.get_twitch_disable_ads():
            command.append("--twitch-disable-ads")
        command.append(url)

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024  # 1MB limit
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=config.get_streamlink_timeout_liveness()
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                error = TimeoutError(f"Timeout expired checking liveness for: {url}", url=url)
                self.logger.warning(f"Timeout expired checking liveness for: {url}")
                return StreamCheckResult(is_live=False, url=url, error=error)

            stdout_text = stdout.decode('utf-8', errors='ignore')
            stderr_text = stderr.decode('utf-8', errors='ignore')

            if process.returncode == 0 and "Available streams:" in stdout_text:
                self.logger.debug(f"Stream is live: {url}")
                return StreamCheckResult(is_live=True, url=url)

            # Stream is not live or error occurred
            error = categorize_streamlink_error(
                stderr=stderr_text,
                stdout=stdout_text,
                return_code=process.returncode,
                url=url,
            )

            if isinstance(error, StreamNotFoundError):
                self.logger.info(f"Stream is not live: {url} - {error}")
            else:
                self.logger.warning(f"Stream check failed: {url} - {error}")

            return StreamCheckResult(is_live=False, url=url, error=error)

        except Exception as e:
            error = StreamlinkError(f"Unexpected error checking liveness: {str(e)}", url=url)
            self.logger.exception(f"Error checking liveness for {url}")
            return StreamCheckResult(is_live=False, url=url, error=error)

    async def _run_streamlink_metadata_async(self, url: str) -> MetadataResult:
        """Run streamlink metadata fetch asynchronously."""
        command = ["streamlink", "--json", url]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024  # 1MB limit
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=config.get_streamlink_timeout_metadata()
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                error = TimeoutError(f"Timeout fetching JSON metadata for {url}", url=url)
                self.logger.warning(f"Timeout fetching JSON metadata for {url}")
                return MetadataResult(success=False, url=url, error=error)

            stdout_text = stdout.decode('utf-8', errors='ignore')
            stderr_text = stderr.decode('utf-8', errors='ignore')

            if process.returncode == 0 and stdout_text.strip():
                try:
                    # Validate JSON format
                    json.loads(stdout_text)
                    return MetadataResult(success=True, json_data=stdout_text.strip(), url=url)
                except json.JSONDecodeError as e:
                    error = StreamlinkError(
                        f"Invalid JSON response: {str(e)}",
                        url=url,
                        stdout=stdout_text
                    )
                    self.logger.warning(f"Could not process JSON for {url}: {e}")
                    return MetadataResult(success=False, url=url, error=error)

            # Metadata fetch failed
            error = categorize_streamlink_error(
                stderr=stderr_text,
                stdout=stdout_text,
                return_code=process.returncode,
                url=url,
            )
            
            self.logger.warning(f"streamlink --json for {url} failed - {error}")
            return MetadataResult(success=False, url=url, error=error)

        except Exception as e:
            error = StreamlinkError(f"Unexpected error fetching metadata: {str(e)}", url=url)
            self.logger.exception(f"Error fetching JSON metadata for {url}")
            return MetadataResult(success=False, url=url, error=error)

    def _create_stream_info_from_metadata(self, url: str, result: MetadataResult, stream_data: Dict[str, str]) -> Optional[StreamInfo]:
        """Create StreamInfo object from metadata result."""
        # Default values
        category = "N/A"
        viewer_count = None
        title = None
        
        # Extract metadata if successful
        if result.success and result.json_data:
            try:
                metadata_json = json.loads(result.json_data)
                if "metadata" in metadata_json:
                    meta = metadata_json["metadata"]
                    title = meta.get("title")
                    
                    # Extract viewer count
                    for key in ["viewers", "viewer_count", "online"]:
                        if key in meta and meta[key] is not None:
                            try:
                                viewer_count = int(meta[key])
                                if viewer_count >= 0:
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # Extract and sanitize category
                    platform = stream_data.get("platform", "Unknown")
                    raw_category = extract_category_keywords((True, result.json_data), platform)
                    category = sanitize_category_string(raw_category)
                    
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.debug(f"Could not parse metadata for {url}: {e}")
        
        return StreamInfo(
            url=url,
            alias=stream_data.get("alias", "Unnamed"),
            platform=stream_data.get("platform", "Unknown"),
            username=stream_data.get("username", "unknown"),
            category=category,
            title=title,
            viewer_count=viewer_count,
            status=StreamStatus.LIVE,
        )


# Factory function for creating async stream checker
def create_async_stream_checker(max_concurrent: int = None) -> AsyncStreamChecker:
    """
    Create async stream checker instance.
    
    Args:
        max_concurrent: Maximum concurrent operations
        
    Returns:
        AsyncStreamChecker instance
    """
    return AsyncStreamChecker(max_concurrent=max_concurrent)


# Async wrapper functions for backward compatibility
async def fetch_live_streams_async(all_configured_streams_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Async version of fetch_live_streams for backward compatibility.
    
    Args:
        all_configured_streams_data: List of configured stream dictionaries
        
    Returns:
        List of live stream info dictionaries
    """
    checker = create_async_stream_checker()
    return await checker.fetch_live_streams_async(all_configured_streams_data)


async def check_multiple_streams_async(urls: List[str]) -> List[Tuple[str, StreamResult]]:
    """
    Check multiple streams concurrently.
    
    Args:
        urls: List of stream URLs to check
        
    Returns:
        List of (url, result) tuples
    """
    checker = create_async_stream_checker()
    return await checker.check_multiple_streams_async(urls)
