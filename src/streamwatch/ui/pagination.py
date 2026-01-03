"""
Pagination and lazy loading utilities for StreamWatch UI.

This module provides pagination, search, and filtering capabilities for large stream lists,
improving performance and user experience when dealing with many streams.
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

from .. import config
from ..core.models import StreamInfo, StreamMetadata, StreamStatus

logger = logging.getLogger(config.APP_NAME + ".ui.pagination")


@dataclass
class PaginationInfo:
    """Information about current pagination state."""

    current_page: int
    total_pages: int
    total_items: int
    page_size: int
    has_next: bool
    has_previous: bool
    start_index: int
    end_index: int

    @classmethod
    def create(
        cls, current_page: int, total_items: int, page_size: int
    ) -> "PaginationInfo":
        """Create pagination info with calculated values."""
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        current_page = max(0, min(current_page, total_pages - 1))

        start_index = current_page * page_size
        end_index = min(start_index + page_size, total_items)

        return cls(
            current_page=current_page,
            total_pages=total_pages,
            total_items=total_items,
            page_size=page_size,
            has_next=current_page < total_pages - 1,
            has_previous=current_page > 0,
            start_index=start_index,
            end_index=end_index,
        )


@dataclass
class FilterCriteria:
    """Criteria for filtering streams."""

    search_term: str = ""
    category_filter: str = ""
    status_filter: Optional[StreamStatus] = None
    platform_filter: str = ""
    show_offline: bool = True

    def is_empty(self) -> bool:
        """Check if no filters are applied."""
        return (
            not self.search_term
            and not self.category_filter
            and self.status_filter is None
            and not self.platform_filter
        )

    def matches(self, stream: StreamInfo) -> bool:
        """Check if a stream matches the filter criteria."""
        # Search term filter (searches alias, username, and category)
        if self.search_term:
            search_lower = self.search_term.lower()
            if not (
                search_lower in stream.alias.lower()
                or search_lower in stream.username.lower()
                or search_lower in stream.category.lower()
            ):
                return False

        # Category filter
        if self.category_filter:
            if self.category_filter.lower() not in stream.category.lower():
                return False

        # Status filter
        if self.status_filter is not None:
            if stream.status != self.status_filter:
                return False

        # Platform filter
        if self.platform_filter:
            if self.platform_filter.lower() not in stream.platform.lower():
                return False

        # Show offline filter
        if not self.show_offline and stream.status == StreamStatus.OFFLINE:
            return False

        return True


class StreamListManager:
    """
    Manages pagination, filtering, and lazy loading for stream lists.

    Provides efficient handling of large stream lists with search, filtering,
    and pagination capabilities.
    """

    def __init__(self, page_size: Optional[int] = None):
        """
        Initialize the stream list manager.

        Args:
            page_size: Number of streams per page (uses config default if None)
        """
        self.page_size = page_size or config.get_streams_per_page()
        self.current_page = 0
        self.filter_criteria = FilterCriteria()
        self._cached_filtered_streams: Optional[List[StreamInfo]] = None
        self._cache_invalidated = True

        logger.debug(f"StreamListManager initialized with page_size={self.page_size}")

    def get_page(
        self, streams: List[StreamInfo], page: Optional[int] = None
    ) -> Tuple[List[StreamInfo], PaginationInfo]:
        """
        Get a specific page of streams with applied filters.

        Args:
            streams: Full list of streams
            page: Page number (0-based), uses current_page if None

        Returns:
            Tuple of (page_streams, pagination_info)
        """
        if page is not None:
            self.current_page = page

        # Apply filters and get filtered streams
        filtered_streams = self._get_filtered_streams(streams)

        # Create pagination info
        pagination_info = PaginationInfo.create(
            current_page=self.current_page,
            total_items=len(filtered_streams),
            page_size=self.page_size,
        )

        # Get streams for current page
        page_streams = filtered_streams[
            pagination_info.start_index : pagination_info.end_index
        ]

        logger.debug(
            f"Retrieved page {pagination_info.current_page + 1}/{pagination_info.total_pages} "
            f"({len(page_streams)} streams, {pagination_info.total_items} total after filtering)"
        )

        return page_streams, pagination_info

    def next_page(
        self, streams: List[StreamInfo]
    ) -> Tuple[List[StreamInfo], PaginationInfo]:
        """Go to next page."""
        filtered_streams = self._get_filtered_streams(streams)
        total_pages = max(
            1, (len(filtered_streams) + self.page_size - 1) // self.page_size
        )

        if self.current_page < total_pages - 1:
            self.current_page += 1
            logger.debug(f"Advanced to page {self.current_page + 1}")

        return self.get_page(streams)

    def previous_page(
        self, streams: List[StreamInfo]
    ) -> Tuple[List[StreamInfo], PaginationInfo]:
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            logger.debug(f"Moved back to page {self.current_page + 1}")

        return self.get_page(streams)

    def first_page(
        self, streams: List[StreamInfo]
    ) -> Tuple[List[StreamInfo], PaginationInfo]:
        """Go to first page."""
        self.current_page = 0
        logger.debug("Moved to first page")
        return self.get_page(streams)

    def last_page(
        self, streams: List[StreamInfo]
    ) -> Tuple[List[StreamInfo], PaginationInfo]:
        """Go to last page."""
        filtered_streams = self._get_filtered_streams(streams)
        total_pages = max(
            1, (len(filtered_streams) + self.page_size - 1) // self.page_size
        )
        self.current_page = total_pages - 1
        logger.debug(f"Moved to last page ({self.current_page + 1})")
        return self.get_page(streams)

    def set_search_filter(self, search_term: str) -> None:
        """
        Set search filter and reset to first page.

        Args:
            search_term: Term to search for in alias, username, and category
        """
        old_term = self.filter_criteria.search_term
        self.filter_criteria.search_term = search_term.strip()

        if old_term != self.filter_criteria.search_term:
            self.current_page = 0
            self._invalidate_cache()
            logger.debug(f"Search filter set to: '{self.filter_criteria.search_term}'")

    def set_category_filter(self, category: str) -> None:
        """
        Set category filter and reset to first page.

        Args:
            category: Category to filter by
        """
        old_category = self.filter_criteria.category_filter
        self.filter_criteria.category_filter = category.strip()

        if old_category != self.filter_criteria.category_filter:
            self.current_page = 0
            self._invalidate_cache()
            logger.debug(
                f"Category filter set to: '{self.filter_criteria.category_filter}'"
            )

    def set_status_filter(self, status: Optional[StreamStatus]) -> None:
        """
        Set status filter and reset to first page.

        Args:
            status: Status to filter by (None for all statuses)
        """
        old_status = self.filter_criteria.status_filter
        self.filter_criteria.status_filter = status

        if old_status != self.filter_criteria.status_filter:
            self.current_page = 0
            self._invalidate_cache()
            logger.debug(f"Status filter set to: {status}")

    def set_platform_filter(self, platform: str) -> None:
        """
        Set platform filter and reset to first page.

        Args:
            platform: Platform to filter by
        """
        old_platform = self.filter_criteria.platform_filter
        self.filter_criteria.platform_filter = platform.strip()

        if old_platform != self.filter_criteria.platform_filter:
            self.current_page = 0
            self._invalidate_cache()
            logger.debug(
                f"Platform filter set to: '{self.filter_criteria.platform_filter}'"
            )

    def toggle_show_offline(self) -> None:
        """Toggle showing offline streams."""
        self.filter_criteria.show_offline = not self.filter_criteria.show_offline
        self.current_page = 0
        self._invalidate_cache()
        logger.debug(f"Show offline toggled to: {self.filter_criteria.show_offline}")

    def clear_filters(self) -> None:
        """Clear all filters and reset to first page."""
        old_criteria = self.filter_criteria
        self.filter_criteria = FilterCriteria()

        if not old_criteria.is_empty():
            self.current_page = 0
            self._invalidate_cache()
            logger.debug("All filters cleared")

    def get_filter_summary(self) -> str:
        """Get a summary of active filters."""
        if self.filter_criteria.is_empty():
            return ""

        parts = []

        if self.filter_criteria.search_term:
            parts.append(f"Search: '{self.filter_criteria.search_term}'")

        if self.filter_criteria.category_filter:
            parts.append(f"Category: '{self.filter_criteria.category_filter}'")

        if self.filter_criteria.status_filter:
            parts.append(f"Status: {self.filter_criteria.status_filter.value}")

        if self.filter_criteria.platform_filter:
            parts.append(f"Platform: '{self.filter_criteria.platform_filter}'")

        if not self.filter_criteria.show_offline:
            parts.append("Hide offline")

        return " | ".join(parts)

    def get_available_categories(self, streams: List[StreamInfo]) -> List[str]:
        """Get list of unique categories from streams."""
        categories = set()
        for stream in streams:
            if stream.category and stream.category != "N/A":
                categories.add(stream.category)
        return sorted(list(categories))

    def get_available_platforms(self, streams: List[StreamInfo]) -> List[str]:
        """Get list of unique platforms from streams."""
        platforms = set()
        for stream in streams:
            if stream.platform and stream.platform != "Unknown":
                platforms.add(stream.platform)
        return sorted(list(platforms))

    def _get_filtered_streams(self, streams: List[StreamInfo]) -> List[StreamInfo]:
        """Get filtered streams with caching."""
        if not self._cache_invalidated and self._cached_filtered_streams is not None:
            return self._cached_filtered_streams

        if self.filter_criteria.is_empty():
            filtered_streams = streams
        else:
            filtered_streams = [
                stream for stream in streams if self.filter_criteria.matches(stream)
            ]

        self._cached_filtered_streams = filtered_streams
        self._cache_invalidated = False

        logger.debug(f"Filtered {len(streams)} streams to {len(filtered_streams)}")
        return filtered_streams

    def _invalidate_cache(self) -> None:
        """Invalidate the filtered streams cache."""
        self._cache_invalidated = True
        self._cached_filtered_streams = None


class LazyStreamLoader:
    """
    Lazy loader for stream metadata to optimize memory usage.

    Only loads detailed stream information when needed, using LRU caching
    to keep frequently accessed streams in memory.
    """

    def __init__(self, cache_size: Optional[int] = None):
        """
        Initialize the lazy loader and dynamically create the cached function.
        """
        from .. import stream_checker  # Local import to avoid circular dependencies

        self.cache_size = cache_size or config.get_metadata_cache_size()
        logger.debug(f"LazyStreamLoader initialized with cache_size={self.cache_size}")

        # Define the core fetching logic as a local function
        def _fetch_details_uncached(stream: StreamInfo) -> StreamInfo:
            """The actual workhorse function that fetches data."""
            logger.debug(f"Cache miss. Lazily fetching details for {stream.url}")
            metadata_result = stream_checker.get_stream_metadata_json_detailed(
                stream.url
            )

            if not metadata_result.success or not metadata_result.json_data:
                return stream

            try:
                metadata_json = json.loads(metadata_result.json_data)
                stream_metadata = StreamMetadata.from_json(metadata_json)

                updated_stream = stream.model_copy(
                    update={
                        "title": stream_metadata.title,  # <-- ADD THIS LINE
                        "category": stream_metadata.category or stream.category,
                        "viewer_count": stream_metadata.viewer_count,
                        "username": stream_metadata.author or stream.username,
                    }
                )
                return updated_stream
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    f"Failed to decode or parse metadata for {stream.url}: {e}"
                )
                return stream

        # Dynamically create the cached version of the function
        self._get_details_cached = lru_cache(maxsize=self.cache_size)(
            _fetch_details_uncached
        )

    def get_details(self, stream: StreamInfo) -> StreamInfo:
        """
        Gets detailed stream information using the lazy-loading function.
        """
        return self._get_details_cached(stream)

    def clear_cache(self) -> None:
        """Clear the LRU cache."""
        self._get_details_cached.cache_clear()
        logger.debug("Stream details cache cleared")

    def get_cache_info(self) -> dict:
        """Get cache statistics."""
        info = self._get_details_cached.cache_info()
        return {
            "hits": info.hits,
            "misses": info.misses,
            "current_size": info.currsize,
            "max_size": info.maxsize,
        }


# Global instances for easy access
_stream_list_manager: Optional[StreamListManager] = None
_lazy_loader: Optional[LazyStreamLoader] = None


def get_stream_list_manager() -> StreamListManager:
    """Get the global stream list manager instance."""
    global _stream_list_manager
    if _stream_list_manager is None:
        _stream_list_manager = StreamListManager()
    return _stream_list_manager


def get_lazy_loader() -> LazyStreamLoader:
    """Get the global lazy loader instance."""
    global _lazy_loader
    if _lazy_loader is None:
        _lazy_loader = LazyStreamLoader()
    return _lazy_loader


def reset_pagination() -> None:
    """Reset pagination state (mainly for testing)."""
    global _stream_list_manager, _lazy_loader
    _stream_list_manager = None
    _lazy_loader = None
    logger.debug("Pagination state reset")
