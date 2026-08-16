"""Error taxonomy for stream resolution, framework-agnostic.

Backends/CLIs map these to their own HTTP/CLI error surfaces.
"""

BROWSER_ERROR_KEYWORDS = (
    "chromium-based web browser",
    "403 client error: forbidden",
    "browser",
    "cloudflare",
)


def is_browser_error(error_msg: str) -> bool:
    """Detect streamlink errors that require browser automation."""
    error_lower = error_msg.lower()
    return any(keyword in error_lower for keyword in BROWSER_ERROR_KEYWORDS)


class StreamlinkCoreError(Exception):
    """Base exception for streamlink resolution failures."""


class NoPluginError(StreamlinkCoreError):
    """No streamlink plugin is available for the URL."""

    def __init__(self, url: str):
        super().__init__(f"No plugin available for URL: {url}")
        self.url = url


class NoStreamsError(StreamlinkCoreError):
    """The plugin resolved but no streams were available (offline)."""

    def __init__(self, url: str):
        super().__init__(f"No streams found for URL: {url}")
        self.url = url


class BrowserRequiredError(StreamlinkCoreError):
    """The platform requires browser automation (anti-bot protection)."""

    def __init__(self, url: str, platform: str = ""):
        super().__init__(f"Browser automation required for {platform or url}: {url}")
        self.url = url
        self.platform = platform


class PluginError(StreamlinkCoreError):
    """Generic plugin failure during resolution."""

    def __init__(self, url: str, message: str, platform: str = ""):
        super().__init__(message)
        self.url = url
        self.message = message
        self.platform = platform


def classify_error(url: str, platform: str, error_msg: str) -> StreamlinkCoreError:
    """Map a streamlink error message to the core taxonomy."""
    if is_browser_error(error_msg):
        return BrowserRequiredError(url, platform=platform)
    return PluginError(url, error_msg, platform=platform)
