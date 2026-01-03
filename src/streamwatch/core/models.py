"""
Data models for StreamWatch application.

This module defines the core data structures used throughout the application
using Pydantic for enhanced validation, serialization, and type safety.
"""

import subprocess
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Import validation utilities
try:
    from ..validation.validators import CommonValidators

    VALIDATORS_AVAILABLE = True
except ImportError:
    VALIDATORS_AVAILABLE = False


class StreamStatus(str, Enum):
    """Enumeration of possible stream statuses with string serialization support."""

    LIVE = "live"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value


class UrlType(Enum):
    """Enumeration of URL types for stream parsing."""

    CHANNEL = "channel"
    VIDEO = "video"
    CHANNEL_ID = "channel_id"
    GENERIC_FALLBACK = "generic_fallback"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


class PlaybackAction(Enum):
    """Enumeration of playback session actions."""

    RETURN_TO_MAIN = "return_to_main"
    QUIT_APPLICATION = "quit_application"
    STOP_PLAYBACK = "stop_playback"
    CONTINUE = "continue"


class UrlMetadata(BaseModel):
    """Metadata extracted from a stream URL with validation."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    platform: str = Field(
        ..., min_length=1, description="Platform name (e.g., 'Twitch', 'YouTube')"
    )
    username: str = Field(
        ..., min_length=1, description="Username or channel identifier"
    )
    url_type: UrlType = Field(default=UrlType.UNKNOWN, description="Type of URL parsed")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        """Validate and normalize platform name."""
        if not v or not v.strip():
            raise ValueError("Platform cannot be empty")
        return v.strip().title()

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        # Remove common URL artifacts
        username = v.strip().lstrip("@").lower()
        if not username:
            raise ValueError("Username cannot be empty after cleaning")
        return username

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format for backward compatibility."""
        return {
            "platform": self.platform,
            "username": self.username,
            "type": self.url_type.value,
        }


class StreamInfo(BaseModel):
    """Complete information about a stream with comprehensive validation."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    url: str = Field(..., min_length=1, description="Stream URL")
    alias: str = Field(
        ..., min_length=1, description="User-friendly alias for the stream"
    )
    platform: str = Field(default="Unknown", description="Platform name")
    username: str = Field(
        default="unknown_stream", description="Username or channel identifier"
    )
    category: str = Field(default="N/A", description="Stream category or game")
    title: Optional[str] = Field(
        default=None, description="Stream title"
    )  # <-- ADD THIS LINE
    viewer_count: Optional[int] = Field(
        default=None, ge=0, description="Current viewer count"
    )
    status: StreamStatus = Field(
        default=StreamStatus.UNKNOWN, description="Current stream status"
    )
    url_type: UrlType = Field(default=UrlType.UNKNOWN, description="Type of URL")
    last_checked: Optional[datetime] = Field(
        default=None, description="Last time stream was checked"
    )

    @field_validator("url")
    @classmethod
    def validate_url_field(cls, v: str) -> str:
        """Validate URL format with comprehensive security checks."""
        if VALIDATORS_AVAILABLE:
            return CommonValidators.url_validator(v)
        else:
            # Fallback validation if validators not available
            if not v or not v.strip():
                raise ValueError("URL cannot be empty")
            url = v.strip()
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError("Invalid URL format")
            except Exception as e:
                raise ValueError(f"Invalid URL: {e}")
            return url

    @field_validator("alias")
    @classmethod
    def validate_alias_field(cls, v: str) -> str:
        """Validate alias format with security checks."""
        if VALIDATORS_AVAILABLE:
            return CommonValidators.alias_validator(v)
        else:
            if not v or not v.strip():
                raise ValueError("Alias cannot be empty")
            return v.strip()

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        """Validate username format with security checks."""
        if VALIDATORS_AVAILABLE:
            return CommonValidators.username_validator(v)
        else:
            return v.strip() if v else "unknown_stream"

    @field_validator("category")
    @classmethod
    def validate_category_field(cls, v: str) -> str:
        """Validate category format with security checks."""
        if VALIDATORS_AVAILABLE:
            return CommonValidators.category_validator(v)
        else:
            return v.strip() if v else "N/A"

    @field_validator("viewer_count")
    @classmethod
    def validate_viewer_count_field(cls, v: Optional[int]) -> Optional[int]:
        """Validate viewer count."""
        if VALIDATORS_AVAILABLE:
            return CommonValidators.viewer_count_validator(v)
        else:
            if v is not None and v < 0:
                raise ValueError("Viewer count cannot be negative")
            return v

    @field_validator("viewer_count")
    @classmethod
    def validate_viewer_count(cls, v: Optional[int]) -> Optional[int]:
        """Validate viewer count is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Viewer count cannot be negative")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization (backward compatibility)."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StreamInfo":
        """Create StreamInfo from dictionary data, relying on Pydantic's validation."""
        return cls.model_validate(data)

    @classmethod
    def _migrate_legacy_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate legacy data format to current schema."""
        migrated = data.copy()

        # Handle enum string values
        if "status" in migrated and isinstance(migrated["status"], str):
            try:
                migrated["status"] = StreamStatus(migrated["status"])
            except ValueError:
                migrated["status"] = StreamStatus.UNKNOWN

        if "url_type" in migrated and isinstance(migrated["url_type"], str):
            try:
                migrated["url_type"] = UrlType(migrated["url_type"])
            except ValueError:
                migrated["url_type"] = UrlType.UNKNOWN

        # Handle datetime strings
        if "last_checked" in migrated and isinstance(migrated["last_checked"], str):
            try:
                migrated["last_checked"] = datetime.fromisoformat(
                    migrated["last_checked"]
                )
            except ValueError:
                migrated["last_checked"] = None

        # Handle invalid viewer_count
        if "viewer_count" in migrated and migrated["viewer_count"] is not None:
            try:
                migrated["viewer_count"] = int(migrated["viewer_count"])
                if migrated["viewer_count"] < 0:
                    migrated["viewer_count"] = None
            except (ValueError, TypeError):
                migrated["viewer_count"] = None

        # Ensure required fields exist
        if "url" not in migrated or not migrated["url"]:
            migrated["url"] = ""
        if "alias" not in migrated or not migrated["alias"]:
            migrated["alias"] = "Unnamed Stream"

        return migrated


class PlaybackSession(BaseModel):
    """Represents an active playback session with validation."""

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        arbitrary_types_allowed=True,  # For subprocess.Popen
    )

    current_stream: StreamInfo = Field(..., description="Currently playing stream")
    current_quality: str = Field(
        ..., min_length=1, description="Current playback quality"
    )
    all_live_streams: List[StreamInfo] = Field(
        ..., min_length=1, description="All available live streams"
    )
    player_process: Optional[subprocess.Popen] = Field(
        default=None, exclude=True, description="Active player process"
    )
    current_index: int = Field(
        default=0, ge=0, description="Index of current stream in the list"
    )
    user_intent_direction: int = Field(
        default=0, ge=-1, le=1, description="User navigation intent"
    )
    session_start_time: datetime = Field(
        default_factory=datetime.now, description="When the session started"
    )
    total_streams_played: int = Field(
        default=1, ge=1, description="Total number of streams played in this session"
    )

    @field_validator("current_quality")
    @classmethod
    def validate_quality(cls, v: str) -> str:
        """Validate quality string."""
        return CommonValidators.quality_validator(v)

    @field_validator("all_live_streams")
    @classmethod
    def validate_streams_list(cls, v: List[StreamInfo]) -> List[StreamInfo]:
        """Validate streams list is not empty."""
        if not v:
            raise ValueError("Must have at least one live stream")
        return v

    @model_validator(mode="after")
    def validate_current_stream_in_list(self) -> "PlaybackSession":
        """Ensure current stream is in the live streams list."""
        # Find current stream by URL to avoid object comparison issues
        found_index = None
        for idx, stream in enumerate(self.all_live_streams):
            if stream.url == self.current_stream.url:
                found_index = idx
                break

        if found_index is not None:
            # Update current_index to match the stream position
            object.__setattr__(self, "current_index", found_index)
        else:
            # Current stream not found, add it to the list
            new_streams = [self.current_stream] + list(self.all_live_streams)
            object.__setattr__(self, "all_live_streams", new_streams)
            object.__setattr__(self, "current_index", 0)

        return self

    def get_next_stream(self) -> Optional[StreamInfo]:
        """Get the next stream in the list."""
        if not self.all_live_streams:
            return None
        next_index = (self.current_index + 1) % len(self.all_live_streams)
        return self.all_live_streams[next_index]

    def get_previous_stream(self) -> Optional[StreamInfo]:
        """Get the previous stream in the list."""
        if not self.all_live_streams:
            return None
        prev_index = (self.current_index - 1) % len(self.all_live_streams)
        return self.all_live_streams[prev_index]

    def switch_to_stream(self, stream: StreamInfo) -> bool:
        """Switch to a specific stream and update session state."""
        try:
            self.current_index = self.all_live_streams.index(stream)
            self.current_stream = stream
            self.total_streams_played += 1
            return True
        except ValueError:
            return False


class StreamMetadata(BaseModel):
    """Metadata from streamlink JSON output with validation."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="allow",  # Allow extra fields for raw_metadata
    )

    title: Optional[str] = Field(default=None, description="Stream title")
    author: Optional[str] = Field(default=None, description="Stream author/channel")
    category: Optional[str] = Field(default=None, description="Stream category/game")
    viewer_count: Optional[int] = Field(
        default=None, ge=0, description="Current viewer count"
    )
    raw_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Raw metadata from streamlink"
    )

    @field_validator("viewer_count")
    @classmethod
    def validate_viewer_count(cls, v: Optional[int]) -> Optional[int]:
        """Validate viewer count is non-negative."""
        if v is not None and v < 0:
            return None  # Invalid viewer counts become None
        return v

    @classmethod
    def from_json(cls, json_data: Optional[Dict[str, Any]]) -> "StreamMetadata":
        """Create StreamMetadata from streamlink JSON output."""
        if not json_data or "metadata" not in json_data:
            return cls()

        meta = json_data["metadata"]

        # Extract viewer count from various possible keys
        viewer_count = None
        for key in ["viewers", "viewer_count", "online"]:
            if key in meta and meta[key] is not None:
                try:
                    viewer_count = int(meta[key])
                    if viewer_count >= 0:  # Only accept non-negative values
                        break
                except (ValueError, TypeError):
                    continue

        return cls(
            title=meta.get("title"),
            author=meta.get("author"),
            category=meta.get("category"),
            viewer_count=viewer_count,
            raw_metadata=meta,
        )


class ConfigSection(BaseModel):
    """Represents a configuration section with typed access and validation."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="allow"
    )

    section_name: str = Field(
        ..., min_length=1, description="Configuration section name"
    )
    values: Dict[str, str] = Field(
        default_factory=dict, description="Configuration key-value pairs"
    )

    def get_str(self, key: str, default: str = "") -> str:
        """Get string value with default."""
        return self.values.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer value with default."""
        try:
            return int(self.values.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean value with default."""
        value = self.values.get(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float value with default."""
        try:
            return float(self.values.get(key, str(default)))
        except (ValueError, TypeError):
            return default


class AppConfig(BaseModel):
    """Complete application configuration with validation."""

    model_config = ConfigDict(
        validate_assignment=True, extra="forbid", str_strip_whitespace=True
    )

    # Core settings
    config_file_path: Optional[Path] = Field(
        default=None, description="Path to configuration file"
    )

    # Player settings
    player_command: str = Field(
        default="mpv", min_length=1, description="Media player command"
    )
    player_args: List[str] = Field(
        default_factory=list, description="Additional player arguments"
    )
    default_quality: str = Field(default="best", description="Default stream quality")

    # Stream checking settings
    max_workers_liveness: int = Field(
        default=10, ge=1, le=50, description="Max concurrent liveness checks"
    )
    max_workers_metadata: int = Field(
        default=5, ge=1, le=20, description="Max concurrent metadata fetches"
    )
    streamlink_timeout_liveness: int = Field(
        default=10, ge=1, le=60, description="Streamlink timeout for liveness checks"
    )
    streamlink_timeout_metadata: int = Field(
        default=15, ge=1, le=120, description="Streamlink timeout for metadata"
    )

    # Cache settings
    cache_enabled: bool = Field(
        default=True, description="Enable stream status caching"
    )
    cache_ttl_seconds: int = Field(
        default=300, ge=60, le=3600, description="Cache TTL in seconds"
    )
    cache_auto_cleanup: bool = Field(
        default=True, description="Enable automatic cache cleanup"
    )
    cache_cleanup_interval: int = Field(
        default=600, ge=300, le=7200, description="Cache cleanup interval"
    )

    # Rate limiting settings
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_global_requests_per_second: float = Field(
        default=8.0, gt=0, le=100, description="Global rate limit"
    )
    rate_limit_global_burst_capacity: int = Field(
        default=15, ge=1, le=100, description="Global burst capacity"
    )

    # Resilience settings
    retry_max_attempts: int = Field(
        default=3, ge=1, le=10, description="Maximum retry attempts"
    )
    retry_base_delay: float = Field(
        default=1.0, gt=0, le=10, description="Base retry delay in seconds"
    )
    circuit_breaker_enabled: bool = Field(
        default=True, description="Enable circuit breaker"
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5, ge=1, le=20, description="Circuit breaker failure threshold"
    )
    circuit_breaker_recovery_timeout: float = Field(
        default=60.0, gt=0, le=600, description="Circuit breaker recovery timeout"
    )

    # UI settings
    refresh_interval: float = Field(
        default=2.0, gt=0.1, le=10, description="UI refresh interval in seconds"
    )
    show_offline_streams: bool = Field(
        default=False, description="Show offline streams in UI"
    )

    # Pagination settings
    streams_per_page: int = Field(
        default=20, ge=5, le=100, description="Number of streams per page"
    )
    enable_search: bool = Field(
        default=True, description="Enable stream search functionality"
    )
    enable_category_filter: bool = Field(
        default=True, description="Enable category filtering"
    )
    enable_platform_filter: bool = Field(
        default=True, description="Enable platform filtering"
    )

    # Memory optimization settings
    metadata_cache_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum cached stream metadata entries",
    )
    lazy_load_threshold: int = Field(
        default=50, ge=20, le=500, description="Stream count threshold for lazy loading"
    )

    @field_validator("player_command")
    @classmethod
    def validate_player_command(cls, v: str) -> str:
        """Validate player command is not empty."""
        if not v or not v.strip():
            raise ValueError("Player command cannot be empty")
        return v.strip()

    @field_validator("config_file_path")
    @classmethod
    def validate_config_path(cls, v: Optional[Path]) -> Optional[Path]:
        """Validate config file path if provided."""
        if v is not None:
            if not isinstance(v, Path):
                v = Path(v)
            # Don't validate existence here as file might not exist yet
        return v

    @model_validator(mode="after")
    def validate_worker_limits(self) -> "AppConfig":
        """Ensure worker limits are reasonable."""
        if self.max_workers_metadata > self.max_workers_liveness:
            # Metadata workers should not exceed liveness workers
            self.max_workers_metadata = min(
                self.max_workers_metadata, self.max_workers_liveness
            )
        return self


def create_playback_session(
    current_stream: StreamInfo, quality: str, all_streams: List[StreamInfo], **kwargs
) -> PlaybackSession:
    """Create PlaybackSession with backward-compatible interface."""
    return PlaybackSession(
        current_stream=current_stream,
        current_quality=quality,
        all_live_streams=all_streams,
        **kwargs,
    )
