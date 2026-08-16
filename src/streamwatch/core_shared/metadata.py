"""Stream metadata extraction: platform detection, categories, viewer counts.

Merges the backend's URL/platform extraction with the CLI's richer
category-keyword and viewer-count logic. This is the canonical copy.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .models import StreamMetadata, UrlMetadata

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

PLATFORM_COLORS = {
    "twitch": "9146FF",
    "youtube": "FF0000",
    "kick": "53FC18",
    "facebook": "1877F2",
    "instagram": "E4405F",
    "tiktok": "000000",
    "bigo": "FF6B35",
    "dailymotion": "0066DC",
    "vimeo": "1AB7EA",
    "steam": "171A21",
    "bilibili": "FB7299",
    "huya": "FF7F00",
    "picarto": "1DA1F2",
    "trovo": "00D7FF",
    "vk": "4680C2",
    "dlive": "FFD700",
    "goodgame": "00AA00",
    "abematv": "00D4AA",
    "aloula": "FF6B6B",
}

PLATFORM_DOMAINS = {
    "twitch.tv": "twitch",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "kick.com": "kick",
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "bigo.tv": "bigo",
    "dailymotion.com": "dailymotion",
    "vimeo.com": "vimeo",
    "steamcommunity.com": "steam",
    "bilibili.com": "bilibili",
    "huya.com": "huya",
    "picarto.tv": "picarto",
    "trovo.live": "trovo",
    "vk.com": "vk",
    "dlive.tv": "dlive",
    "goodgame.ru": "goodgame",
    "abema.tv": "abematv",
    "aloula.sa": "aloula",
}


def extract_platform_from_url(url: str) -> str:
    """Extract the platform name from a URL."""
    try:
        domain = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return "unknown"

    for suffix, platform in PLATFORM_DOMAINS.items():
        if suffix in domain:
            return platform

    try:
        name = domain.split(".")[0]
        return name if name else "unknown"
    except Exception:
        return "unknown"


def _result(platform: str, username: str, url_type: str = "unknown") -> Dict[str, str]:
    return {"platform": platform, "username": username, "type": url_type}


def parse_url_metadata(url: str) -> UrlMetadata:
    """Parse platform, a preliminary username/ID, and URL type from a URL."""
    if (
        not isinstance(url, str)
        or not url.strip()
        or not url.lower().startswith(("http://", "https://"))
    ):
        return UrlMetadata(
            platform="Unknown", username="unknown_stream", url_type="parse_error"
        )

    try:
        parsed_uri = urlparse(url)
        netloc = parsed_uri.netloc.replace("www.", "")
        path = parsed_uri.path
    except ValueError:
        return UrlMetadata(
            platform="Unknown", username="unknown_stream", url_type="parse_error"
        )

    # Twitch channel
    if "twitch.tv" in netloc:
        m = re.match(r"/([a-zA-Z0-9_]{4,25})/?$", path)
        if m:
            return UrlMetadata(
                platform="Twitch", username=m.group(1), url_type="channel"
            )
        return UrlMetadata(
            platform="Twitch", username="unknown_user", url_type="parse_error"
        )

    # YouTube channel / video
    if "youtube.com" in netloc or "youtu.be" in netloc:
        channel_match = re.match(
            r"/(?:@([a-zA-Z0-9_.-]+)|c/([a-zA-Z0-9_.-]+)|channel/([a-zA-Z0-9_-]+)|user/([a-zA-Z0-9_.-]+))/?",
            path,
        )
        if channel_match:
            username = next(
                (g for g in channel_match.groups() if g is not None), "unknown_channel"
            )
            return UrlMetadata(
                platform="YouTube", username=username, url_type="channel"
            )
        video_id_match = re.search(r"(?:/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
        if video_id_match:
            return UrlMetadata(
                platform="YouTube", username=video_id_match.group(1), url_type="video"
            )
        return UrlMetadata(
            platform="YouTube", username="unknown_youtube_url", url_type="parse_error"
        )

    # Kick channel
    if "kick.com" in netloc:
        m = re.match(r"/([a-zA-Z0-9_]+)/?$", path)
        if m:
            return UrlMetadata(platform="Kick", username=m.group(1), url_type="channel")
        return UrlMetadata(
            platform="Kick", username="unknown_user", url_type="parse_error"
        )

    # Generic fallback
    try:
        domain_parts = netloc.split(".")
        platform_name = domain_parts[-2] if len(domain_parts) > 1 else domain_parts[0]
    except IndexError:
        platform_name = "Unknown"

    path_parts = [part for part in path.split("/") if part]
    username_guess = path_parts[-1] if path_parts else netloc

    return UrlMetadata(
        platform=platform_name, username=username_guess, url_type="generic_fallback"
    )


# ---------------------------------------------------------------------------
# Thumbnails and stream types
# ---------------------------------------------------------------------------


def generate_fallback_thumbnail(platform: str, author: str) -> str:
    """Generate a fallback thumbnail URL based on platform brand colors."""
    author = author or "default"
    color = PLATFORM_COLORS.get(platform.lower(), "6B7280")
    text_color = "FFFFFF" if platform.lower() != "kick" else "000000"
    return (
        f"https://ui-avatars.com/api/?name={author}&size=300"
        f"&background={color}&color={text_color}&format=png"
    )


def get_stream_types_from_streams(streams: dict) -> List[str]:
    """Extract the set of available stream types (HLS/HTTP/DASH/...) from streams."""
    stream_types = set()
    for stream in streams.values():
        stream_type = type(stream).__name__.replace("Stream", "").lower()
        if stream_type == "hls":
            stream_types.add("HLS")
        elif stream_type == "http":
            stream_types.add("HTTP")
        elif stream_type == "dash":
            stream_types.add("DASH")
        else:
            stream_types.add(stream_type.upper())
    return sorted(stream_types)


# ---------------------------------------------------------------------------
# Category / keyword extraction
# ---------------------------------------------------------------------------

# Clean common live-stream title prefixes
_COMMON_PREFIX_RE = re.compile(
    r"^\(?(LIVE|EN DIRECT|ОНЛАЙН|생방송|ライブ)[\]:]*\s*", re.IGNORECASE
)

# Short words that should not lead a YouTube category guess
_SKIP_FIRST_WORDS = {
    "A",
    "AN",
    "BE",
    "IN",
    "IS",
    "IT",
    "OF",
    "ON",
    "OR",
    "SO",
    "TO",
    "EL",
    "LA",
    "DE",
}


def _clean_common_prefixes(text: str) -> str:
    return _COMMON_PREFIX_RE.sub("", text).strip()


def extract_category_from_json(
    metadata_json: Any, platform: str, url_type: str = "unknown"
) -> str:
    """Extract a category/keywords string from parsed streamlink JSON metadata."""
    if not metadata_json or "metadata" not in metadata_json:
        return "N/A"
    meta = metadata_json.get("metadata", {})
    title = meta.get("title", "")

    platform_key = platform.lower()

    if platform_key == "twitch":
        return str(meta.get("game") or (title.split(" ")[0] if title else "N/A"))

    if platform_key == "youtube":
        clean_title = _clean_common_prefixes(title)
        words = clean_title.split()
        if (
            len(words) > 1
            and len(words[0]) <= 2
            and words[0].upper() not in _SKIP_FIRST_WORDS
        ):
            return " ".join(words[1:4])
        return " ".join(words[:3]) if words else "N/A"

    if platform_key == "kick":
        if ":" in title:
            return title.split(":")[0].strip()
        return title.split(" ")[0] if title else "N/A"

    if platform_key in {"tiktok", "douyin", "bigo live"}:
        return _clean_common_prefixes(title) if title else "N/A"

    if platform_key == "bilibili":
        category = meta.get("game_name", meta.get("category"))
        if category:
            return str(category)
        if " - " in title:
            return _clean_common_prefixes(title).split(" - ")[0]
        return title.split(" ")[0] if title else "N/A"

    return "N/A"


def extract_category_keywords(
    metadata_result: Tuple[bool, str], platform: str, url_type: str = "unknown"
) -> str:
    """Extract category/keywords from streamlink JSON metadata (string form)."""
    success, json_data = metadata_result
    if not success:
        return "N/A"
    try:
        metadata_json = json.loads(json_data)
    except json.JSONDecodeError:
        return "N/A"
    return extract_category_from_json(metadata_json, platform, url_type)


# ---------------------------------------------------------------------------
# Viewer count extraction
# ---------------------------------------------------------------------------

_VIEWER_KEYS = ("viewers", "viewer_count", "online")


def extract_viewer_count(meta: Dict[str, Any]) -> Optional[int]:
    """Extract a viewer count from metadata, returning None if unknown."""
    for key in _VIEWER_KEYS:
        if key in meta:
            try:
                value = int(meta[key])
                if value >= 0:
                    return value
            except (TypeError, ValueError):
                continue
    return None


def normalize_stream_metadata(
    meta: Dict[str, Any], platform: str, author_fallback: str = ""
) -> StreamMetadata:
    """Build a normalized StreamMetadata from a plugin's raw metadata dict."""
    author = meta.get("author") or author_fallback
    title = meta.get("title") or "Live Stream"
    return StreamMetadata(
        title=title,
        author=author,
        category=meta.get("category") or meta.get("game") or "",
        stream_id=meta.get("id") or "",
        platform=platform,
        thumbnail=generate_fallback_thumbnail(platform, author),
        viewer_count=extract_viewer_count(meta),
    )
