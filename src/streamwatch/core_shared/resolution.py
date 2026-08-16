"""Stream resolution: resolve a URL to online/offline/error + details.

Framework-agnostic core extracted from the backend's stream service.
Consumers bring their own session pool instance, caching, and error surface.
"""

import logging
from typing import Any, Dict, Optional

from streamlink.exceptions import (
    NoPluginError,
    NoStreamsError,
    PluginError as SLPluginError,
)
from streamlink.session import Streamlink

from .errors import (
    BrowserRequiredError,
    NoPluginError as CoreNoPluginError,
    NoStreamsError as CoreNoStreamsError,
    PluginError as CorePluginError,
    classify_error,
    is_browser_error,
)
from .metadata import (
    extract_platform_from_url,
    generate_fallback_thumbnail,
    get_stream_types_from_streams,
    normalize_stream_metadata,
)
from .models import StreamResolution, StreamStatus

logger = logging.getLogger(__name__)

# Suppress streamlink's noisy plugin-loading logs
logging.getLogger("streamlink.session.plugins").setLevel(logging.CRITICAL)
logging.getLogger("streamlink.plugins").setLevel(logging.CRITICAL)
logging.getLogger("streamlink").setLevel(logging.ERROR)


def configure_twitch_session(session: Streamlink, oauth_token: str = "") -> None:
    """Apply Twitch-specific session options if configured."""
    try:
        session.set_option("twitch-supported-codecs", "h264,h265,av1")
        session.set_option("twitch-low-latency", True)
        if oauth_token:
            session.set_option(
                "twitch-api-header", f"Authorization=OAuth {oauth_token}"
            )
    except Exception as e:
        logger.debug("Twitch session options not applied: %s", e)


class StreamResolver:
    """Resolves stream URLs using a caller-provided session pool."""

    def __init__(self, session_pool, twitch_oauth_token: str = ""):
        self.session_pool = session_pool
        self.twitch_oauth_token = twitch_oauth_token

    def _configure_session(self, session: Streamlink, platform: str) -> None:
        if platform == "twitch":
            configure_twitch_session(session, self.twitch_oauth_token)

    def check_status(self, url: str) -> StreamStatus:
        """Check the liveness status of a single URL."""
        session = self.session_pool.get_session()
        try:
            platform = extract_platform_from_url(url)
            self._configure_session(session, platform)

            plugin_name, plugin_class, resolved_url = session.resolve_url(url)
            plugin_instance = plugin_class(session, resolved_url)
            streams = plugin_instance.streams()

            if not streams:
                return StreamStatus(url=url, status="offline", platform=platform)

            metadata = normalize_stream_metadata(
                plugin_instance.get_metadata(), platform, author_fallback=plugin_name
            )
            return StreamStatus(
                url=url,
                status="online",
                title=metadata.title,
                author=metadata.author,
                thumbnail=metadata.thumbnail,
                category=metadata.category,
                stream_id=metadata.stream_id,
                platform=platform,
            )
        except NoPluginError:
            return StreamStatus(
                url=url,
                status="error",
                error="No plugin available for this URL",
                platform=extract_platform_from_url(url),
            )
        except NoStreamsError:
            return StreamStatus(
                url=url,
                status="offline",
                error="No streams available",
                platform=extract_platform_from_url(url),
            )
        except SLPluginError as e:
            error_msg = str(e)
            platform = extract_platform_from_url(url)
            if is_browser_error(error_msg):
                return StreamStatus(
                    url=url,
                    status="error",
                    error="Browser dependency required",
                    platform=platform,
                    error_details={
                        "type": "browser_required",
                        "message": f"{platform.title()} requires browser automation",
                        "reason": "Platform uses anti-bot protection",
                    },
                )
            return StreamStatus(
                url=url,
                status="error",
                error=f"Plugin error: {error_msg}",
                platform=platform,
            )
        except Exception as e:
            return StreamStatus(
                url=url,
                status="error",
                error=f"Unexpected error: {e!s}",
                platform=extract_platform_from_url(url),
            )
        finally:
            self.session_pool.return_session(session)

    def resolve(self, url: str) -> StreamResolution:
        """Resolve full stream details including playback URLs."""
        session = self.session_pool.get_session()
        try:
            platform = extract_platform_from_url(url)
            self._configure_session(session, platform)

            plugin_name, plugin_class, resolved_url = session.resolve_url(url)
            plugin_instance = plugin_class(session, resolved_url)
            streams = plugin_instance.streams()

            if not streams:
                return StreamResolution(
                    status="offline", original_url=url, platform=platform
                )

            metadata = plugin_instance.get_metadata()
            author = metadata.get("author") or plugin_name

            return StreamResolution(
                status="online",
                title=metadata.get("title") or "Live Stream",
                author=author,
                thumbnail=generate_fallback_thumbnail(platform, author),
                best_quality=streams.get("best").url if streams.get("best") else None,
                all_qualities={name: s.url for name, s in streams.items()},
                category=metadata.get("category") or "",
                stream_id=metadata.get("id") or "",
                platform=platform,
                stream_types=get_stream_types_from_streams(streams),
                original_url=url,
            )
        except NoPluginError:
            raise CoreNoPluginError(url)
        except NoStreamsError:
            raise CoreNoStreamsError(url)
        except SLPluginError as e:
            raise classify_error(url, extract_platform_from_url(url), str(e))
        except Exception as e:
            raise CorePluginError(url, f"Unexpected error: {e!s}")
        finally:
            self.session_pool.return_session(session)


def resolve_stream_details(
    session_pool, url: str, twitch_oauth_token: str = ""
) -> StreamResolution:
    """Convenience: resolve details with an ad-hoc pool (no cached resolver)."""
    return StreamResolver(session_pool, twitch_oauth_token).resolve(url)
