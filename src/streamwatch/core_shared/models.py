"""Domain models shared across StreamWatch consumers."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StreamStatus(BaseModel):
    """Status of a single stream URL after a liveness check."""

    url: str
    status: str = Field(description="online | offline | error")
    title: str = ""
    author: str = ""
    thumbnail: str = ""
    error: str = ""
    category: str = ""
    stream_id: str = ""
    platform: str = ""
    error_details: Optional[Dict[str, Any]] = None


class StreamResolution(BaseModel):
    """Full stream details including playback URLs."""

    status: str = Field(description="online | offline | error")
    title: Optional[str] = None
    author: Optional[str] = None
    thumbnail: Optional[str] = None
    best_quality: Optional[str] = None
    all_qualities: Optional[Dict[str, str]] = None
    error: Optional[str] = None
    original_url: Optional[str] = None
    category: Optional[str] = None
    stream_id: Optional[str] = None
    platform: Optional[str] = None
    stream_types: Optional[List[str]] = None
    error_details: Optional[Dict[str, Any]] = None


class UrlMetadata(BaseModel):
    """Parsed platform/username/type from a stream URL."""

    platform: str = "Unknown"
    username: str = "unknown_stream"
    url_type: str = "unknown"


class StreamMetadata(BaseModel):
    """Normalized metadata extracted from a stream."""

    title: str = ""
    author: str = ""
    category: str = ""
    stream_id: str = ""
    platform: str = ""
    thumbnail: str = ""
    viewer_count: Optional[int] = None
    stream_types: List[str] = Field(default_factory=list)
