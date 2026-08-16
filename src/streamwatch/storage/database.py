"""
SQLite database integration for StreamWatch application.

This module provides database operations for storing streams, status history,
configuration, and user preferences with ACID compliance and advanced querying.
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import config
from ..core.models import StreamInfo, StreamStatus

logger = logging.getLogger(config.APP_NAME + ".database")

# Database schema version for migrations
SCHEMA_VERSION = 2

# SQL schema definitions
SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Platform information
CREATE TABLE IF NOT EXISTS platforms (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    base_url TEXT,
    rate_limit_requests_per_second REAL DEFAULT 2.0,
    rate_limit_burst_capacity INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Core streams table
CREATE TABLE IF NOT EXISTS streams (
    url TEXT PRIMARY KEY,
    alias TEXT NOT NULL,
    platform_id INTEGER,
    username TEXT,
    category TEXT DEFAULT 'N/A',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);

-- Stream status history for analytics
CREATE TABLE IF NOT EXISTS stream_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_url TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('live', 'offline', 'error', 'unknown')),
    viewer_count INTEGER,
    title TEXT,
    category TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_time_ms INTEGER,
    error_message TEXT,
    FOREIGN KEY (stream_url) REFERENCES streams(url) ON DELETE CASCADE
);

-- Application configuration
CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    data_type TEXT NOT NULL CHECK (data_type IN ('string', 'integer', 'float', 'boolean', 'json')),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- User preferences per stream
CREATE TABLE IF NOT EXISTS stream_preferences (
    stream_url TEXT PRIMARY KEY,
    preferred_quality TEXT DEFAULT 'best',
    auto_open BOOLEAN DEFAULT FALSE,
    notification_enabled BOOLEAN DEFAULT TRUE,
    custom_player_args TEXT,
    last_watched TIMESTAMP,
    watch_count INTEGER DEFAULT 0,
    FOREIGN KEY (stream_url) REFERENCES streams(url) ON DELETE CASCADE
);

-- Stream tags table
CREATE TABLE IF NOT EXISTS stream_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_url TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#007acc',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stream_url) REFERENCES streams(url) ON DELETE CASCADE,
    UNIQUE(stream_url, name)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_stream_checks_url_time ON stream_checks(stream_url, checked_at);
CREATE INDEX IF NOT EXISTS idx_stream_checks_status ON stream_checks(status);
CREATE INDEX IF NOT EXISTS idx_stream_checks_time ON stream_checks(checked_at);
CREATE INDEX IF NOT EXISTS idx_streams_platform ON streams(platform_id);
CREATE INDEX IF NOT EXISTS idx_streams_active ON streams(is_active);
CREATE INDEX IF NOT EXISTS idx_streams_alias ON streams(alias);
CREATE INDEX IF NOT EXISTS idx_stream_tags_url ON stream_tags(stream_url);

-- Insert default platforms
INSERT OR IGNORE INTO platforms (name, base_url, rate_limit_requests_per_second, rate_limit_burst_capacity) VALUES
    ('Twitch', 'https://twitch.tv/', 3.0, 8),
    ('YouTube', 'https://youtube.com/', 2.0, 6),
    ('Kick', 'https://kick.com/', 4.0, 10),
    ('Unknown', '', 2.0, 5);
"""


class DatabaseError(Exception):
    """Base exception for database operations."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails."""

    pass




class StreamDatabase:
    """
    Thread-safe SQLite database interface for StreamWatch.

    Provides ACID-compliant operations for streams, status history,
    configuration, and user preferences.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            db_path = self._get_default_db_path()

        self.db_path = Path(db_path)
        self._local = threading.local()
        self._closed = False

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._initialize_database()

        logger.info(f"Database initialized at: {self.db_path}")

    def _get_default_db_path(self) -> Path:
        """Get default database path in user config directory."""
        config_dir = Path.home() / ".config" / "streamwatch"
        return config_dir / "streamwatch.db"

    @property
    def connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if self._closed:
            raise DatabaseConnectionError("Database has been closed")

        if not hasattr(self._local, "connection") or self._local.connection is None:
            try:
                conn = sqlite3.connect(
                    str(self.db_path),
                    timeout=30.0,  # 30 second timeout
                    check_same_thread=False,
                )

                # Configure connection
                conn.row_factory = sqlite3.Row  # Enable dict-like access
                conn.execute(
                    "PRAGMA foreign_keys = ON"
                )  # Enable foreign key constraints
                conn.execute(
                    "PRAGMA journal_mode = WAL"
                )  # Write-Ahead Logging for better concurrency
                conn.execute(
                    "PRAGMA synchronous = NORMAL"
                )  # Balance safety and performance
                conn.execute("PRAGMA temp_store = MEMORY")  # Use memory for temp tables
                conn.execute("PRAGMA cache_size = -64000")  # 64MB cache

                self._local.connection = conn

            except sqlite3.Error as e:
                raise DatabaseConnectionError(f"Failed to connect to database: {e}")

        return self._local.connection

    @contextmanager
    def get_connection(self):
        """Context manager for safe database connection access."""
        conn = self.connection
        try:
            yield conn
        except Exception:
            # Connection might be in bad state, clear it
            if hasattr(self._local, "connection"):
                try:
                    self._local.connection.close()
                except Exception:
                    pass
                self._local.connection = None
            raise

    @contextmanager
    def transaction(self) -> sqlite3.Connection:
        """Context manager for database transactions."""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction rolled back: {e}")
                raise

    def _initialize_database(self) -> None:
        """Initialize database schema and default data."""
        try:
            with self.transaction() as conn:
                # Execute schema
                conn.executescript(SCHEMA_SQL)

                # Check/update schema version
                current_version = self._get_schema_version()
                if current_version < SCHEMA_VERSION:
                    self._migrate_schema(conn, current_version, SCHEMA_VERSION)
                    logger.info(f"Database schema updated to v{SCHEMA_VERSION}")

                logger.debug("Database schema initialized successfully")

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to initialize database: {e}")

    def _migrate_schema(self, conn: sqlite3.Connection, from_version: int, to_version: int) -> None:
        """Migrate database schema between versions."""
        logger.info(f"Migrating database schema from v{from_version} to v{to_version}")

        # The v2 stream_tags table and its index are already created by SCHEMA_SQL
        # (CREATE TABLE/INDEX IF NOT EXISTS run on every init), so no DDL is
        # needed here. Future migrations add their DDL in this method.

        # Update schema version
        conn.execute(
            "INSERT INTO schema_info (version, description) VALUES (?, ?)",
            (to_version, f"Schema migration to version {to_version}"),
        )

        logger.info(f"Database migration completed: v{from_version} -> v{to_version}")

    def _get_schema_version(self) -> int:
        """Get current database schema version."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT MAX(version) FROM schema_info")
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except sqlite3.Error:
            return 0

    def close(self) -> None:
        """Close database connection and mark as closed."""
        if not self._closed:
            if hasattr(self._local, "connection") and self._local.connection:
                try:
                    self._local.connection.close()
                except Exception as e:
                    logger.warning(f"Error closing database connection: {e}")
                finally:
                    self._local.connection = None
            self._closed = True
            logger.debug("Database connection closed")

    def __del__(self):
        """Destructor to ensure connections are closed."""
        try:
            self.close()
        except Exception:
            # Ignore errors during cleanup
            pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()

    def get_database_info(self) -> Dict[str, Any]:
        """Get database information for debugging."""
        try:
            cursor = self.connection.execute("PRAGMA database_list")
            db_info = cursor.fetchall()

            cursor = self.connection.execute("SELECT COUNT(*) FROM streams")
            stream_count = cursor.fetchone()[0]

            cursor = self.connection.execute("SELECT COUNT(*) FROM stream_checks")
            check_count = cursor.fetchone()[0]

            return {
                "database_path": str(self.db_path),
                "database_size_bytes": (
                    self.db_path.stat().st_size if self.db_path.exists() else 0
                ),
                "schema_version": self._get_schema_version(),
                "stream_count": stream_count,
                "check_count": check_count,
                "database_info": [dict(row) for row in db_info],
            }

        except sqlite3.Error as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}

    # --- Stream Operations ---

    def save_stream(self, stream: StreamInfo) -> None:
        """
        Insert or update a stream in the database.

        Args:
            stream: StreamInfo object to save
        """
        try:
            with self.transaction() as conn:
                # Get or create platform
                platform_id = self._get_or_create_platform(stream.platform)

                # Insert or update stream
                conn.execute(
                    """
                    INSERT OR REPLACE INTO streams
                    (url, alias, platform_id, username, category, last_modified, is_active)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, TRUE)
                """,
                    (
                        stream.url,
                        stream.alias,
                        platform_id,
                        stream.username,
                        stream.category,
                    ),
                )

                logger.debug(f"Saved stream: {stream.alias} ({stream.url})")

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to save stream: {e}")

    def load_streams(self, include_inactive: bool = False) -> List[StreamInfo]:
        """
        Load all streams from the database.

        Args:
            include_inactive: Whether to include inactive streams

        Returns:
            List of StreamInfo objects
        """
        try:
            query = """
                SELECT s.url, s.alias, p.name as platform, s.username, s.category,
                       s.added_at, s.last_modified, s.user_notes, s.is_active,
                       sc.status, sc.viewer_count, sc.checked_at
                FROM streams s
                LEFT JOIN platforms p ON s.platform_id = p.id
                LEFT JOIN (
                    SELECT stream_url, status, viewer_count, checked_at,
                           ROW_NUMBER() OVER (PARTITION BY stream_url ORDER BY checked_at DESC) as rn
                    FROM stream_checks
                ) sc ON s.url = sc.stream_url AND sc.rn = 1
            """

            if not include_inactive:
                query += " WHERE s.is_active = TRUE"

            query += " ORDER BY s.alias"

            with self.get_connection() as conn:
                cursor = conn.execute(query)
                rows = cursor.fetchall()

            streams = []
            for row in rows:
                # Parse status
                status = StreamStatus.UNKNOWN
                if row["status"]:
                    try:
                        status = StreamStatus(row["status"])
                    except ValueError:
                        status = StreamStatus.UNKNOWN

                # Parse last_checked
                last_checked = None
                if row["checked_at"]:
                    try:
                        last_checked = datetime.fromisoformat(row["checked_at"])
                    except ValueError:
                        pass

                stream = StreamInfo(
                    url=row["url"],
                    alias=row["alias"],
                    platform=row["platform"] or "Unknown",
                    username=row["username"] or "unknown_stream",
                    category=row["category"] or "N/A",
                    viewer_count=row["viewer_count"],
                    status=status,
                    last_checked=last_checked,
                )

                streams.append(stream)

            logger.debug(f"Loaded {len(streams)} streams from database")
            return streams

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to load streams: {e}")

    def get_stream(self, url: str) -> Optional[StreamInfo]:
        """
        Get a specific stream by URL.

        Args:
            url: Stream URL to look up

        Returns:
            StreamInfo object or None if not found
        """
        try:
            cursor = self.connection.execute(
                """
                SELECT s.url, s.alias, p.name as platform, s.username, s.category,
                       sc.status, sc.viewer_count, sc.checked_at
                FROM streams s
                LEFT JOIN platforms p ON s.platform_id = p.id
                LEFT JOIN (
                    SELECT stream_url, status, viewer_count, checked_at,
                           ROW_NUMBER() OVER (PARTITION BY stream_url ORDER BY checked_at DESC) as rn
                    FROM stream_checks
                ) sc ON s.url = sc.stream_url AND sc.rn = 1
                WHERE s.url = ? AND s.is_active = TRUE
            """,
                (url,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            # Parse status and last_checked (same logic as load_streams)
            status = StreamStatus.UNKNOWN
            if row["status"]:
                try:
                    status = StreamStatus(row["status"])
                except ValueError:
                    status = StreamStatus.UNKNOWN

            last_checked = None
            if row["checked_at"]:
                try:
                    last_checked = datetime.fromisoformat(row["checked_at"])
                except ValueError:
                    pass

            return StreamInfo(
                url=row["url"],
                alias=row["alias"],
                platform=row["platform"] or "Unknown",
                username=row["username"] or "unknown_stream",
                category=row["category"] or "N/A",
                viewer_count=row["viewer_count"],
                status=status,
                last_checked=last_checked,
            )

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get stream: {e}")

    def delete_stream(self, url: str) -> bool:
        """
        Marks an active stream as inactive in the database.

        Args:
            url: Stream URL to deactivate.

        Returns:
            True if an active stream was successfully marked as inactive, False otherwise.
        """
        try:
            with self.transaction() as conn:
                # Only update the row if it is currently active
                cursor = conn.execute(
                    "UPDATE streams SET is_active = FALSE WHERE url = ? AND is_active = TRUE",
                    (url,),
                )
                deactivated = cursor.rowcount > 0

                if deactivated:
                    logger.info(f"Deactivated stream: {url}")

                return deactivated

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to deactivate stream: {e}")

    def _get_or_create_platform(self, platform_name: str) -> int:
        """
        Get platform ID, creating it if it doesn't exist.

        Args:
            platform_name: Name of the platform

        Returns:
            Platform ID
        """
        try:
            with self.get_connection() as conn:
                # Try to get existing platform
                cursor = conn.execute(
                    "SELECT id FROM platforms WHERE name = ?", (platform_name,)
                )
                row = cursor.fetchone()

                if row:
                    return row[0]

                # Create new platform
                cursor = conn.execute(
                    "INSERT INTO platforms (name) VALUES (?)", (platform_name,)
                )

                return cursor.lastrowid

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get/create platform: {e}")

    # --- Stream Status Tracking Operations ---

    def record_stream_check(
        self,
        url: str,
        status: StreamStatus,
        viewer_count: Optional[int] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Record a stream status check result.

        Args:
            url: Stream URL
            status: Stream status
            viewer_count: Current viewer count
            title: Stream title
            category: Stream category
            response_time_ms: Response time in milliseconds
            error_message: Error message if status is ERROR
        """
        try:
            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO stream_checks
                    (stream_url, status, viewer_count, title, category,
                     response_time_ms, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        url,
                        status.value,
                        viewer_count,
                        title,
                        category,
                        response_time_ms,
                        error_message,
                    ),
                )

                logger.debug(f"Recorded check for {url}: {status.value}")

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to record stream check: {e}")

    def get_stream_history(self, url: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get historical status data for a stream.

        Args:
            url: Stream URL
            days: Number of days of history to retrieve

        Returns:
            List of check records
        """
        try:
            cursor = self.connection.execute(
                """
                SELECT status, viewer_count, title, category, checked_at,
                       response_time_ms, error_message
                FROM stream_checks
                WHERE stream_url = ? AND checked_at > datetime('now', '-' || ? || ' days')
                ORDER BY checked_at DESC
            """,
                (url, str(days)),
            )

            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get stream history: {e}")

    def get_live_streams(self) -> List[StreamInfo]:
        """
        Get currently live streams efficiently.

        Returns:
            List of live StreamInfo objects
        """
        try:
            cursor = self.connection.execute(
                """
                SELECT s.url, s.alias, p.name as platform, s.username, s.category,
                       sc.viewer_count, sc.checked_at
                FROM streams s
                JOIN platforms p ON s.platform_id = p.id
                JOIN (
                    SELECT stream_url, status, viewer_count, checked_at,
                           ROW_NUMBER() OVER (PARTITION BY stream_url ORDER BY checked_at DESC) as rn
                    FROM stream_checks
                    WHERE status = 'live'
                ) sc ON s.url = sc.stream_url AND sc.rn = 1
                WHERE s.is_active = TRUE
                ORDER BY sc.viewer_count DESC NULLS LAST, s.alias
            """
            )

            streams = []
            for row in cursor.fetchall():
                last_checked = None
                if row["checked_at"]:
                    try:
                        last_checked = datetime.fromisoformat(row["checked_at"])
                    except ValueError:
                        pass

                stream = StreamInfo(
                    url=row["url"],
                    alias=row["alias"],
                    platform=row["platform"],
                    username=row["username"] or "unknown_stream",
                    category=row["category"] or "N/A",
                    viewer_count=row["viewer_count"],
                    status=StreamStatus.LIVE,
                    last_checked=last_checked,
                )
                streams.append(stream)

            logger.debug(f"Found {len(streams)} live streams")
            return streams

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get live streams: {e}")

    def search_streams(self, query: str, limit: int = 50) -> List[StreamInfo]:
        """
        Search streams by alias, platform, username, or category.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching StreamInfo objects
        """
        try:
            search_pattern = f"%{query}%"

            cursor = self.connection.execute(
                """
                SELECT s.url, s.alias, p.name as platform, s.username, s.category,
                       sc.status, sc.viewer_count, sc.checked_at
                FROM streams s
                LEFT JOIN platforms p ON s.platform_id = p.id
                LEFT JOIN (
                    SELECT stream_url, status, viewer_count, checked_at,
                           ROW_NUMBER() OVER (PARTITION BY stream_url ORDER BY checked_at DESC) as rn
                    FROM stream_checks
                ) sc ON s.url = sc.stream_url AND sc.rn = 1
                WHERE s.is_active = TRUE AND (
                    s.alias LIKE ? OR
                    p.name LIKE ? OR
                    s.username LIKE ? OR
                    s.category LIKE ?
                )
                ORDER BY
                    CASE WHEN sc.status = 'live' THEN 0 ELSE 1 END,
                    sc.viewer_count DESC NULLS LAST,
                    s.alias
                LIMIT ?
            """,
                (search_pattern, search_pattern, search_pattern, search_pattern, limit),
            )

            streams = []
            for row in cursor.fetchall():
                # Parse status and last_checked (same logic as before)
                status = StreamStatus.UNKNOWN
                if row["status"]:
                    try:
                        status = StreamStatus(row["status"])
                    except ValueError:
                        status = StreamStatus.UNKNOWN

                last_checked = None
                if row["checked_at"]:
                    try:
                        last_checked = datetime.fromisoformat(row["checked_at"])
                    except ValueError:
                        pass

                stream = StreamInfo(
                    url=row["url"],
                    alias=row["alias"],
                    platform=row["platform"] or "Unknown",
                    username=row["username"] or "unknown_stream",
                    category=row["category"] or "N/A",
                    viewer_count=row["viewer_count"],
                    status=status,
                    last_checked=last_checked,
                )
                streams.append(stream)

            logger.debug(f"Search '{query}' returned {len(streams)} results")
            return streams

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to search streams: {e}")

    # --- Analytics Operations ---

    def get_stream_analytics(self, url: str, days: int = 30) -> Dict[str, Any]:
        """
        Get analytics data for a stream.

        Args:
            url: Stream URL
            days: Number of days to analyze

        Returns:
            Dictionary with analytics data
        """
        try:
            # Get basic stats
            cursor = self.connection.execute(
                """
                SELECT
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'live' THEN 1 ELSE 0 END) as live_checks,
                    AVG(CASE WHEN status = 'live' THEN viewer_count END) as avg_viewers,
                    MAX(CASE WHEN status = 'live' THEN viewer_count END) as peak_viewers,
                    AVG(response_time_ms) as avg_response_time
                FROM stream_checks
                WHERE stream_url = ? AND checked_at > datetime('now', '-' || ? || ' days')
            """,
                (url, str(days)),
            )

            stats = dict(cursor.fetchone())

            # Calculate uptime percentage
            uptime_percent = 0.0
            if stats["total_checks"] > 0:
                uptime_percent = (stats["live_checks"] / stats["total_checks"]) * 100

            # Get hourly distribution
            cursor = self.connection.execute(
                """
                SELECT
                    strftime('%H', checked_at) as hour,
                    COUNT(*) as checks,
                    SUM(CASE WHEN status = 'live' THEN 1 ELSE 0 END) as live_checks
                FROM stream_checks
                WHERE stream_url = ? AND checked_at > datetime('now', '-' || ? || ' days')
                GROUP BY strftime('%H', checked_at)
                ORDER BY hour
            """,
                (url, str(days)),
            )

            hourly_data = [dict(row) for row in cursor.fetchall()]

            return {
                "url": url,
                "period_days": days,
                "total_checks": stats["total_checks"] or 0,
                "live_checks": stats["live_checks"] or 0,
                "uptime_percent": round(uptime_percent, 2),
                "avg_viewers": int(stats["avg_viewers"]) if stats["avg_viewers"] else 0,
                "peak_viewers": stats["peak_viewers"] or 0,
                "avg_response_time_ms": (
                    int(stats["avg_response_time"]) if stats["avg_response_time"] else 0
                ),
                "hourly_distribution": hourly_data,
            }

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get stream analytics: {e}")

    def get_platform_stats(self) -> List[Dict[str, Any]]:
        """
        Get statistics by platform.

        Returns:
            List of platform statistics
        """
        try:
            cursor = self.connection.execute(
                """
                SELECT
                    p.name as platform,
                    COUNT(DISTINCT s.url) as total_streams,
                    COUNT(DISTINCT CASE WHEN sc.status = 'live' THEN s.url END) as live_streams,
                    AVG(CASE WHEN sc.status = 'live' THEN sc.viewer_count END) as avg_viewers
                FROM platforms p
                LEFT JOIN streams s ON p.id = s.platform_id AND s.is_active = TRUE
                LEFT JOIN (
                    SELECT stream_url, status, viewer_count,
                           ROW_NUMBER() OVER (PARTITION BY stream_url ORDER BY checked_at DESC) as rn
                    FROM stream_checks
                ) sc ON s.url = sc.stream_url AND sc.rn = 1
                GROUP BY p.name
                HAVING total_streams > 0
                ORDER BY total_streams DESC
            """
            )

            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get platform stats: {e}")

    # --- Configuration Operations ---

    def save_config_value(self, key: str, value: Any, description: str = "") -> None:
        """
        Save a configuration value to the database.

        Args:
            key: Configuration key
            value: Configuration value
            description: Optional description
        """
        try:
            # Determine data type and serialize value
            if isinstance(value, bool):
                data_type = "boolean"
                value_str = "true" if value else "false"
            elif isinstance(value, int):
                data_type = "integer"
                value_str = str(value)
            elif isinstance(value, float):
                data_type = "float"
                value_str = str(value)
            elif isinstance(value, (dict, list)):
                data_type = "json"
                import json

                value_str = json.dumps(value)
            else:
                data_type = "string"
                value_str = str(value)

            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO app_config (key, value, data_type, description, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (key, value_str, data_type, description),
                )

                logger.debug(f"Saved config: {key} = {value}")

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to save config value: {e}")

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value from the database.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        try:
            cursor = self.connection.execute(
                "SELECT value, data_type FROM app_config WHERE key = ?", (key,)
            )

            row = cursor.fetchone()
            if not row:
                return default

            value_str, data_type = row

            # Deserialize based on data type
            if data_type == "boolean":
                return value_str.lower() == "true"
            elif data_type == "integer":
                return int(value_str)
            elif data_type == "float":
                return float(value_str)
            elif data_type == "json":
                import json

                return json.loads(value_str)
            else:
                return value_str

        except (sqlite3.Error, ValueError, TypeError) as e:
            logger.warning(f"Failed to get config value '{key}': {e}")
            return default

    def get_all_config(self) -> Dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            Dictionary of all configuration values
        """
        try:
            cursor = self.connection.execute(
                "SELECT key, value, data_type FROM app_config"
            )

            config_dict = {}
            for row in cursor.fetchall():
                key, value_str, data_type = row

                # Deserialize value (same logic as get_config_value)
                try:
                    if data_type == "boolean":
                        config_dict[key] = value_str.lower() == "true"
                    elif data_type == "integer":
                        config_dict[key] = int(value_str)
                    elif data_type == "float":
                        config_dict[key] = float(value_str)
                    elif data_type == "json":
                        import json

                        config_dict[key] = json.loads(value_str)
                    else:
                        config_dict[key] = value_str
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to deserialize config '{key}': {e}")
                    config_dict[key] = value_str

            return config_dict

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get all config: {e}")

    # --- Stream Tags Operations ---

    def add_stream_tag(self, stream_url: str, tag_name: str, color: str = "#007acc") -> bool:
        """
        Add a tag to a stream.

        Args:
            stream_url: Stream URL
            tag_name: Tag name
            color: Tag color (hex format)

        Returns:
            True if tag was added, False if it already exists
        """
        try:
            with self.transaction() as conn:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO stream_tags (stream_url, name, color) VALUES (?, ?, ?)",
                    (stream_url, tag_name, color)
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to add stream tag: {e}")

    def get_stream_tags(self, stream_url: str) -> List[Dict[str, Any]]:
        """
        Get all tags for a stream.

        Args:
            stream_url: Stream URL

        Returns:
            List of tag dictionaries
        """
        try:
            cursor = self.connection.execute(
                "SELECT name, color, created_at FROM stream_tags WHERE stream_url = ? ORDER BY name",
                (stream_url,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get stream tags: {e}")

    def remove_stream_tag(self, stream_url: str, tag_name: str) -> bool:
        """
        Remove a tag from a stream.

        Args:
            stream_url: Stream URL
            tag_name: Tag name to remove

        Returns:
            True if tag was removed, False if it didn't exist
        """
        try:
            with self.transaction() as conn:
                cursor = conn.execute(
                    "DELETE FROM stream_tags WHERE stream_url = ? AND name = ?",
                    (stream_url, tag_name)
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to remove stream tag: {e}")


# Global database instance
_database_instance: Optional[StreamDatabase] = None
_database_lock = threading.Lock()


def get_database() -> StreamDatabase:
    """
    Get the global database instance, creating it if necessary.

    Returns:
        The global StreamDatabase instance
    """
    global _database_instance

    with _database_lock:
        if _database_instance is None:
            _database_instance = StreamDatabase()

        return _database_instance


def reset_database() -> None:
    """Reset the global database instance (mainly for testing)."""
    global _database_instance

    with _database_lock:
        if _database_instance:
            _database_instance.close()
        _database_instance = None
        logger.info("Reset global database instance")
