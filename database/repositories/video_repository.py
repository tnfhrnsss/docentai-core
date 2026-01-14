"""
Video Repository
da_videos 테이블에 대한 CRUD 작업을 담당합니다.
"""
import json
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime


class VideoRepository:
    """Repository for video metadata operations"""

    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize repository with database connection

        Args:
            conn: SQLite database connection
        """
        self.conn = conn

    def create(
        self,
        video_id: str,
        platform: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Create new video record

        Args:
            video_id: Video identifier (e.g., Netflix ID, YouTube ID)
            platform: Platform name (e.g., 'netflix', 'youtube')
            title: Video title
            metadata: Additional metadata as dictionary

        Returns:
            int: Created record ID

        Raises:
            sqlite3.IntegrityError: If video_id already exists
        """
        cursor = self.conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute(
            """
            INSERT INTO da_videos (video_id, platform, title, metadata)
            VALUES (?, ?, ?, ?)
        """,
            (video_id, platform, title, metadata_json),
        )

        self.conn.commit()
        record_id = cursor.lastrowid
        cursor.close()

        return record_id

    def get_by_video_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get video by video_id

        Args:
            video_id: Video identifier

        Returns:
            Optional[Dict]: Video record or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, video_id, platform, title, metadata, created_at
            FROM da_videos
            WHERE video_id = ?
        """,
            (video_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return self._row_to_dict(row)
        return None

    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        Get video by internal ID

        Args:
            record_id: Internal record ID

        Returns:
            Optional[Dict]: Video record or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, video_id, platform, title, metadata, created_at
            FROM da_videos
            WHERE id = ?
        """,
            (record_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return self._row_to_dict(row)
        return None

    def exists(self, video_id: str) -> bool:
        """
        Check if video exists

        Args:
            video_id: Video identifier

        Returns:
            bool: True if exists, False otherwise
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT 1 FROM da_videos WHERE video_id = ?
        """,
            (video_id,),
        )

        exists = cursor.fetchone() is not None
        cursor.close()

        return exists

    def update(
        self,
        video_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update video record

        Args:
            video_id: Video identifier
            title: New title (if provided)
            metadata: New metadata (if provided)

        Returns:
            bool: True if updated, False if not found
        """
        cursor = self.conn.cursor()

        # Build dynamic update query
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        params.append(video_id)
        query = f"UPDATE da_videos SET {', '.join(updates)} WHERE video_id = ?"

        cursor.execute(query, params)
        self.conn.commit()

        updated = cursor.rowcount > 0
        cursor.close()

        return updated

    def delete(self, video_id: str) -> bool:
        """
        Delete video record

        Args:
            video_id: Video identifier

        Returns:
            bool: True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM da_videos WHERE video_id = ?
        """,
            (video_id,),
        )

        self.conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()

        return deleted

    def list_all(
        self, platform: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all videos with optional filtering

        Args:
            platform: Filter by platform (optional)
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[Dict]: List of video records
        """
        cursor = self.conn.cursor()

        if platform:
            cursor.execute(
                """
                SELECT id, video_id, platform, title, metadata, created_at
                FROM da_videos
                WHERE platform = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """,
                (platform, limit, offset),
            )
        else:
            cursor.execute(
                """
                SELECT id, video_id, platform, title, metadata, created_at
                FROM da_videos
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )

        rows = cursor.fetchall()
        cursor.close()

        return [self._row_to_dict(row) for row in rows]

    def count(self, platform: Optional[str] = None) -> int:
        """
        Count total videos

        Args:
            platform: Filter by platform (optional)

        Returns:
            int: Total count
        """
        cursor = self.conn.cursor()

        if platform:
            cursor.execute(
                """
                SELECT COUNT(*) FROM da_videos WHERE platform = ?
            """,
                (platform,),
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM da_videos")

        count = cursor.fetchone()[0]
        cursor.close()

        return count

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Convert SQLite row to dictionary

        Args:
            row: SQLite row object

        Returns:
            Dict: Row as dictionary with parsed metadata
        """
        data = dict(row)

        # Parse metadata JSON
        if data.get("metadata"):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                data["metadata"] = None

        return data
