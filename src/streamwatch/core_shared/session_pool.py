"""Reusable pre-configured Streamlink session pool."""

import queue
import threading
import time
from typing import Optional

from streamlink.session import Streamlink


class StreamlinkSessionPool:
    """Thread-safe pool of pre-configured Streamlink sessions.

    Sessions are periodically refreshed to avoid stale HTTP state.
    """

    def __init__(self, pool_size: int = 3, refresh_interval: float = 3600.0):
        self.pool_size = pool_size
        self.sessions: "queue.Queue[Streamlink]" = queue.Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self.created_at = time.time()
        self.refresh_interval = refresh_interval

        self._create_sessions()

    def _create_session(self) -> Streamlink:
        session = Streamlink()
        session.set_option(
            "http-headers",
            "User-Agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        )
        return session

    def _create_sessions(self) -> None:
        for _ in range(self.pool_size):
            self.sessions.put(self._create_session())

    def get_session(self, timeout: float = 5.0) -> Streamlink:
        """Get a session from the pool (creating a fallback if empty)."""
        try:
            if time.time() - self.created_at > self.refresh_interval:
                self._refresh_pool()
            return self.sessions.get(timeout=timeout)
        except queue.Empty:
            return self._create_session()

    def return_session(self, session: Streamlink) -> None:
        """Return a session to the pool (discarding if the pool is full)."""
        try:
            self.sessions.put_nowait(session)
        except queue.Full:
            pass

    def _refresh_pool(self) -> None:
        with self.lock:
            if time.time() - self.created_at < self.refresh_interval:
                return
            while not self.sessions.empty():
                try:
                    self.sessions.get_nowait()
                except queue.Empty:
                    break
            self._create_sessions()
            self.created_at = time.time()

    def size(self) -> int:
        return self.sessions.qsize()

    def __enter__(self) -> Streamlink:
        return self.get_session()

    def __exit__(self, *exc) -> None:
        # Sessions returned via explicit calls; nothing to release on exit.
        return None
