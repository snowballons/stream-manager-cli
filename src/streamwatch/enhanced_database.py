"""
Enhanced SQLite database with advanced export/import capabilities.
Replaces JSON storage with full SQLite implementation and creative export features.
"""

import csv
import json
import logging
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from .database import StreamDatabase, DatabaseError
from .models import StreamInfo, StreamStatus

logger = logging.getLogger(__name__)


class EnhancedStreamDatabase(StreamDatabase):
    """Enhanced SQLite database with advanced export/import capabilities."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize enhanced database."""
        super().__init__(db_path)
        self._ensure_enhanced_schema()

    def _ensure_enhanced_schema(self) -> None:
        """Ensure enhanced schema tables exist."""
        enhanced_schema = """
        -- Export/Import tracking
        CREATE TABLE IF NOT EXISTS export_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            stream_count INTEGER NOT NULL,
            exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size_bytes INTEGER,
            metadata TEXT
        );

        -- Stream tags for organization
        CREATE TABLE IF NOT EXISTS stream_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#007acc',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stream_tag_assignments (
            stream_url TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (stream_url, tag_id),
            FOREIGN KEY (stream_url) REFERENCES streams(url) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES stream_tags(id) ON DELETE CASCADE
        );

        -- Stream collections/playlists
        CREATE TABLE IF NOT EXISTS stream_collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS collection_streams (
            collection_id INTEGER NOT NULL,
            stream_url TEXT NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (collection_id, stream_url),
            FOREIGN KEY (collection_id) REFERENCES stream_collections(id) ON DELETE CASCADE,
            FOREIGN KEY (stream_url) REFERENCES streams(url) ON DELETE CASCADE
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_export_history_type ON export_history(export_type);
        CREATE INDEX IF NOT EXISTS idx_stream_tags_name ON stream_tags(name);
        CREATE INDEX IF NOT EXISTS idx_collection_streams_position ON collection_streams(collection_id, position);
        """

        try:
            with self.transaction() as conn:
                conn.executescript(enhanced_schema)
                logger.debug("Enhanced schema initialized")
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to initialize enhanced schema: {e}")

    # --- Advanced Export Features ---

    def export_to_json(self, file_path: Path, include_history: bool = False, 
                      include_analytics: bool = False) -> Dict[str, Any]:
        """Export streams to JSON with optional history and analytics."""
        try:
            streams = self.load_streams(include_inactive=True)
            export_data = {
                "export_info": {
                    "version": "2.0",
                    "exported_at": datetime.now().isoformat(),
                    "stream_count": len(streams),
                    "include_history": include_history,
                    "include_analytics": include_analytics
                },
                "streams": []
            }

            for stream in streams:
                stream_data = stream.model_dump()
                
                if include_history:
                    stream_data["history"] = self.get_stream_history(stream.url, days=30)
                
                if include_analytics:
                    stream_data["analytics"] = self.get_stream_analytics(stream.url, days=30)
                
                # Add tags
                stream_data["tags"] = self.get_stream_tags(stream.url)
                
                export_data["streams"].append(stream_data)

            # Add platform statistics
            export_data["platform_stats"] = self.get_platform_stats()

            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

            # Record export
            file_size = file_path.stat().st_size
            self._record_export("json", str(file_path), len(streams), file_size, {
                "include_history": include_history,
                "include_analytics": include_analytics
            })

            return {
                "success": True,
                "streams_exported": len(streams),
                "file_size": file_size,
                "file_path": str(file_path)
            }

        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_to_csv(self, file_path: Path, include_stats: bool = True) -> Dict[str, Any]:
        """Export streams to CSV format."""
        try:
            streams = self.load_streams()
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['url', 'alias', 'platform', 'username', 'category', 'status', 'added_at']
                
                if include_stats:
                    fieldnames.extend(['viewer_count', 'last_checked', 'uptime_percent', 'avg_viewers'])
                
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for stream in streams:
                    row = {
                        'url': stream.url,
                        'alias': stream.alias,
                        'platform': stream.platform,
                        'username': stream.username,
                        'category': stream.category,
                        'status': stream.status.value,
                        'added_at': stream.last_checked.isoformat() if stream.last_checked else ''
                    }
                    
                    if include_stats:
                        analytics = self.get_stream_analytics(stream.url, days=7)
                        row.update({
                            'viewer_count': stream.viewer_count or 0,
                            'last_checked': stream.last_checked.isoformat() if stream.last_checked else '',
                            'uptime_percent': analytics.get('uptime_percent', 0),
                            'avg_viewers': analytics.get('avg_viewers', 0)
                        })
                    
                    writer.writerow(row)

            file_size = file_path.stat().st_size
            self._record_export("csv", str(file_path), len(streams), file_size)

            return {
                "success": True,
                "streams_exported": len(streams),
                "file_size": file_size,
                "file_path": str(file_path)
            }

        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_to_xml(self, file_path: Path) -> Dict[str, Any]:
        """Export streams to XML format."""
        try:
            streams = self.load_streams()
            
            root = ET.Element("streamwatch_export")
            root.set("version", "2.0")
            root.set("exported_at", datetime.now().isoformat())
            root.set("stream_count", str(len(streams)))
            
            streams_elem = ET.SubElement(root, "streams")
            
            for stream in streams:
                stream_elem = ET.SubElement(streams_elem, "stream")
                stream_elem.set("url", stream.url)
                
                ET.SubElement(stream_elem, "alias").text = stream.alias
                ET.SubElement(stream_elem, "platform").text = stream.platform
                ET.SubElement(stream_elem, "username").text = stream.username
                ET.SubElement(stream_elem, "category").text = stream.category
                ET.SubElement(stream_elem, "status").text = stream.status.value
                
                if stream.viewer_count:
                    ET.SubElement(stream_elem, "viewer_count").text = str(stream.viewer_count)
                
                # Add tags
                tags = self.get_stream_tags(stream.url)
                if tags:
                    tags_elem = ET.SubElement(stream_elem, "tags")
                    for tag in tags:
                        tag_elem = ET.SubElement(tags_elem, "tag")
                        tag_elem.text = tag["name"]
                        tag_elem.set("color", tag["color"])

            # Add platform stats
            stats_elem = ET.SubElement(root, "platform_statistics")
            for stat in self.get_platform_stats():
                platform_elem = ET.SubElement(stats_elem, "platform")
                platform_elem.set("name", stat["platform"])
                platform_elem.set("total_streams", str(stat["total_streams"]))
                platform_elem.set("live_streams", str(stat["live_streams"] or 0))

            # Write to file
            tree = ET.ElementTree(root)
            ET.indent(tree, space="  ", level=0)
            tree.write(file_path, encoding='utf-8', xml_declaration=True)

            file_size = file_path.stat().st_size
            self._record_export("xml", str(file_path), len(streams), file_size)

            return {
                "success": True,
                "streams_exported": len(streams),
                "file_size": file_size,
                "file_path": str(file_path)
            }

        except Exception as e:
            logger.error(f"XML export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_to_m3u(self, file_path: Path, live_only: bool = True) -> Dict[str, Any]:
        """Export streams to M3U playlist format."""
        try:
            if live_only:
                streams = self.get_live_streams()
            else:
                streams = self.load_streams()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                f.write(f"# StreamWatch Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total streams: {len(streams)}\n\n")
                
                for stream in streams:
                    # M3U format: #EXTINF:duration,title
                    title = f"{stream.alias} ({stream.platform})"
                    if stream.viewer_count:
                        title += f" - {stream.viewer_count} viewers"
                    
                    f.write(f"#EXTINF:-1,{title}\n")
                    f.write(f"#EXTGRP:{stream.platform}\n")
                    f.write(f"{stream.url}\n\n")

            file_size = file_path.stat().st_size
            self._record_export("m3u", str(file_path), len(streams), file_size, {"live_only": live_only})

            return {
                "success": True,
                "streams_exported": len(streams),
                "file_size": file_size,
                "file_path": str(file_path)
            }

        except Exception as e:
            logger.error(f"M3U export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_analytics_report(self, file_path: Path, days: int = 30) -> Dict[str, Any]:
        """Export comprehensive analytics report."""
        try:
            streams = self.load_streams()
            
            report_data = {
                "report_info": {
                    "generated_at": datetime.now().isoformat(),
                    "period_days": days,
                    "total_streams": len(streams)
                },
                "summary": {
                    "platform_distribution": {},
                    "total_checks": 0,
                    "total_live_time": 0,
                    "avg_uptime": 0
                },
                "streams": [],
                "platform_stats": self.get_platform_stats()
            }

            total_uptime = 0
            total_checks = 0

            for stream in streams:
                analytics = self.get_stream_analytics(stream.url, days)
                stream_report = {
                    "url": stream.url,
                    "alias": stream.alias,
                    "platform": stream.platform,
                    "analytics": analytics
                }
                report_data["streams"].append(stream_report)
                
                # Aggregate stats
                platform = stream.platform
                if platform not in report_data["summary"]["platform_distribution"]:
                    report_data["summary"]["platform_distribution"][platform] = 0
                report_data["summary"]["platform_distribution"][platform] += 1
                
                total_uptime += analytics.get("uptime_percent", 0)
                total_checks += analytics.get("total_checks", 0)

            # Calculate averages
            if len(streams) > 0:
                report_data["summary"]["avg_uptime"] = round(total_uptime / len(streams), 2)
            report_data["summary"]["total_checks"] = total_checks

            # Write report
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, default=str)

            file_size = file_path.stat().st_size
            self._record_export("analytics", str(file_path), len(streams), file_size, {"days": days})

            return {
                "success": True,
                "streams_analyzed": len(streams),
                "file_size": file_size,
                "file_path": str(file_path)
            }

        except Exception as e:
            logger.error(f"Analytics export failed: {e}")
            return {"success": False, "error": str(e)}

    # --- Import Features ---

    def import_from_json(self, file_path: Path, merge_mode: str = "skip") -> Dict[str, Any]:
        """
        Import streams from JSON file.
        
        Args:
            file_path: Path to JSON file
            merge_mode: "skip", "update", or "replace"
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            streams_data = data.get("streams", [])
            imported_count = 0
            updated_count = 0
            skipped_count = 0

            for stream_data in streams_data:
                url = stream_data.get("url")
                if not url:
                    continue

                existing_stream = self.get_stream(url)
                
                if existing_stream and merge_mode == "skip":
                    skipped_count += 1
                    continue

                # Create StreamInfo object
                stream = StreamInfo(
                    url=url,
                    alias=stream_data.get("alias", "Imported Stream"),
                    platform=stream_data.get("platform", "Unknown"),
                    username=stream_data.get("username", "unknown"),
                    category=stream_data.get("category", "N/A")
                )

                if existing_stream and merge_mode == "update":
                    self.save_stream(stream)
                    updated_count += 1
                elif not existing_stream:
                    self.save_stream(stream)
                    imported_count += 1

                # Import tags if present
                tags = stream_data.get("tags", [])
                for tag_data in tags:
                    if isinstance(tag_data, dict):
                        self.add_stream_tag(url, tag_data["name"], tag_data.get("color", "#007acc"))
                    else:
                        self.add_stream_tag(url, str(tag_data))

            return {
                "success": True,
                "imported": imported_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_processed": len(streams_data)
            }

        except Exception as e:
            logger.error(f"JSON import failed: {e}")
            return {"success": False, "error": str(e)}

    def import_from_m3u(self, file_path: Path) -> Dict[str, Any]:
        """Import streams from M3U playlist."""
        try:
            imported_count = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            current_title = None
            current_group = None
            
            for line in lines:
                line = line.strip()
                
                if line.startswith("#EXTINF:"):
                    # Extract title from #EXTINF:-1,title
                    parts = line.split(",", 1)
                    if len(parts) > 1:
                        current_title = parts[1].strip()
                
                elif line.startswith("#EXTGRP:"):
                    # Extract group/platform
                    current_group = line.replace("#EXTGRP:", "").strip()
                
                elif line and not line.startswith("#"):
                    # This is a URL
                    url = line.strip()
                    
                    # Parse URL to get platform info
                    from .stream_utils import parse_url_metadata
                    parsed_info = parse_url_metadata(url)
                    
                    platform = current_group or parsed_info.get("platform", "Unknown")
                    username = parsed_info.get("username", "unknown")
                    alias = current_title or username
                    
                    # Clean up alias (remove viewer count info)
                    if " - " in alias and "viewers" in alias:
                        alias = alias.split(" - ")[0]
                    if " (" in alias:
                        alias = alias.split(" (")[0]
                    
                    stream = StreamInfo(
                        url=url,
                        alias=alias,
                        platform=platform,
                        username=username
                    )
                    
                    # Only add if not already exists
                    if not self.get_stream(url):
                        self.save_stream(stream)
                        imported_count += 1
                    
                    # Reset for next stream
                    current_title = None
                    current_group = None

            return {
                "success": True,
                "imported": imported_count
            }

        except Exception as e:
            logger.error(f"M3U import failed: {e}")
            return {"success": False, "error": str(e)}

    # --- Tag Management ---

    def add_stream_tag(self, stream_url: str, tag_name: str, color: str = "#007acc") -> None:
        """Add a tag to a stream."""
        try:
            with self.transaction() as conn:
                # Create tag if it doesn't exist
                conn.execute(
                    "INSERT OR IGNORE INTO stream_tags (name, color) VALUES (?, ?)",
                    (tag_name, color)
                )
                
                # Get tag ID
                cursor = conn.execute("SELECT id FROM stream_tags WHERE name = ?", (tag_name,))
                tag_id = cursor.fetchone()[0]
                
                # Assign tag to stream
                conn.execute(
                    "INSERT OR IGNORE INTO stream_tag_assignments (stream_url, tag_id) VALUES (?, ?)",
                    (stream_url, tag_id)
                )

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to add stream tag: {e}")

    def get_stream_tags(self, stream_url: str) -> List[Dict[str, str]]:
        """Get all tags for a stream."""
        try:
            cursor = self.connection.execute(
                """
                SELECT st.name, st.color
                FROM stream_tags st
                JOIN stream_tag_assignments sta ON st.id = sta.tag_id
                WHERE sta.stream_url = ?
                ORDER BY st.name
                """,
                (stream_url,)
            )
            
            return [{"name": row[0], "color": row[1]} for row in cursor.fetchall()]

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get stream tags: {e}")

    def remove_stream_tag(self, stream_url: str, tag_name: str) -> bool:
        """Remove a tag from a stream."""
        try:
            with self.transaction() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM stream_tag_assignments
                    WHERE stream_url = ? AND tag_id = (
                        SELECT id FROM stream_tags WHERE name = ?
                    )
                    """,
                    (stream_url, tag_name)
                )
                return cursor.rowcount > 0

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to remove stream tag: {e}")

    # --- Export History ---

    def _record_export(self, export_type: str, file_path: str, stream_count: int, 
                      file_size: int, metadata: Optional[Dict] = None) -> None:
        """Record an export operation."""
        try:
            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO export_history 
                    (export_type, file_path, stream_count, file_size_bytes, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (export_type, file_path, stream_count, file_size, 
                     json.dumps(metadata) if metadata else None)
                )

        except sqlite3.Error as e:
            logger.warning(f"Failed to record export: {e}")

    def get_export_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get export history."""
        try:
            cursor = self.connection.execute(
                """
                SELECT export_type, file_path, stream_count, file_size_bytes,
                       exported_at, metadata
                FROM export_history
                ORDER BY exported_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            
            history = []
            for row in cursor.fetchall():
                metadata = None
                if row[5]:  # metadata column
                    try:
                        metadata = json.loads(row[5])
                    except json.JSONDecodeError:
                        pass
                
                history.append({
                    "export_type": row[0],
                    "file_path": row[1],
                    "stream_count": row[2],
                    "file_size_bytes": row[3],
                    "exported_at": row[4],
                    "metadata": metadata
                })
            
            return history

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get export history: {e}")

    # --- Backup and Restore ---

    def create_backup(self, backup_path: Path) -> Dict[str, Any]:
        """Create a complete database backup."""
        try:
            # Use SQLite backup API for consistent backup
            with sqlite3.connect(str(backup_path)) as backup_conn:
                self.connection.backup(backup_conn)
            
            file_size = backup_path.stat().st_size
            
            return {
                "success": True,
                "backup_path": str(backup_path),
                "file_size": file_size,
                "created_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {"success": False, "error": str(e)}

    def restore_from_backup(self, backup_path: Path) -> Dict[str, Any]:
        """Restore database from backup."""
        try:
            if not backup_path.exists():
                return {"success": False, "error": "Backup file not found"}

            # Close current connection
            self.close()
            
            # Replace current database with backup
            import shutil
            shutil.copy2(backup_path, self.db_path)
            
            # Reinitialize
            self._closed = False
            self._initialize_database()
            
            return {
                "success": True,
                "restored_from": str(backup_path),
                "restored_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {"success": False, "error": str(e)}


# Factory function
def create_enhanced_database(db_path: Optional[Path] = None) -> EnhancedStreamDatabase:
    """Create enhanced database instance."""
    return EnhancedStreamDatabase(db_path)
