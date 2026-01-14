"""
Reference Repository
da_videos_reference 테이블에 대한 CRUD 작업을 담당합니다.
"""
import json
import sqlite3
from typing import Optional, List, Dict, Any


class ReferenceRepository:
    """Repository for video reference operations (Namuwiki, Wikipedia, etc.)"""

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
        source: str,
        ref_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Create new reference record

        Args:
            video_id: Video identifier
            source: Reference source (e.g., 'namuwiki', 'wikipedia')
            ref_url: Reference URL
            metadata: Additional metadata as dictionary

        Returns:
            int: Created record ID

        Raises:
            sqlite3.IntegrityError: If (video_id, source) already exists
        """
        cursor = self.conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute(
            """
            INSERT INTO da_videos_reference (video_id, source, ref_url, metadata)
            VALUES (?, ?, ?, ?)
        """,
            (video_id, source, ref_url, metadata_json),
        )

        self.conn.commit()
        record_id = cursor.lastrowid
        cursor.close()

        return record_id

    def get_by_video_and_source(
        self, video_id: str, source: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get reference by video_id and source

        Args:
            video_id: Video identifier
            source: Reference source

        Returns:
            Optional[Dict]: Reference record or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, video_id, source, ref_url, metadata, created_at
            FROM da_videos_reference
            WHERE video_id = ? AND source = ?
        """,
            (video_id, source),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return self._row_to_dict(row)
        return None

    def get_all_by_video(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Get all references for a video

        Args:
            video_id: Video identifier

        Returns:
            List[Dict]: List of reference records
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, video_id, source, ref_url, metadata, created_at
            FROM da_videos_reference
            WHERE video_id = ?
            ORDER BY created_at DESC
        """,
            (video_id,),
        )

        rows = cursor.fetchall()
        cursor.close()

        return [self._row_to_dict(row) for row in rows]

    def update(
        self,
        video_id: str,
        source: str,
        ref_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update reference record

        Args:
            video_id: Video identifier
            source: Reference source
            ref_url: New reference URL (if provided)
            metadata: New metadata (if provided)

        Returns:
            bool: True if updated, False if not found
        """
        cursor = self.conn.cursor()

        # Build dynamic update query
        updates = []
        params = []

        if ref_url is not None:
            updates.append("ref_url = ?")
            params.append(ref_url)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        params.extend([video_id, source])
        query = f"UPDATE da_videos_reference SET {', '.join(updates)} WHERE video_id = ? AND source = ?"

        cursor.execute(query, params)
        self.conn.commit()

        updated = cursor.rowcount > 0
        cursor.close()

        return updated

    def delete(self, video_id: str, source: str) -> bool:
        """
        Delete reference record

        Args:
            video_id: Video identifier
            source: Reference source

        Returns:
            bool: True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM da_videos_reference
            WHERE video_id = ? AND source = ?
        """,
            (video_id, source),
        )

        self.conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()

        return deleted

    def delete_all_by_video(self, video_id: str) -> int:
        """
        Delete all references for a video

        Args:
            video_id: Video identifier

        Returns:
            int: Number of deleted records
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM da_videos_reference WHERE video_id = ?
        """,
            (video_id,),
        )

        self.conn.commit()
        deleted_count = cursor.rowcount
        cursor.close()

        return deleted_count

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
