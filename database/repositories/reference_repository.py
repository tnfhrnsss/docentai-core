"""
Reference Repository
da_videos_reference 테이블에 대한 CRUD 작업을 담당합니다.
"""
import json
import sqlite3
from typing import Optional, List, Dict, Any, Union


class ReferenceRepository:
    """Repository for video reference operations (Google Search results, etc.)"""

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
        reference: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Create new reference record

        Args:
            video_id: Video identifier
            reference: Reference content (as bytes or JSON string)
            metadata: Additional metadata as dictionary

        Returns:
            int: Created record ID
        """
        cursor = self.conn.cursor()

        # Convert reference to bytes if it's a string
        if isinstance(reference, str):
            reference_blob = reference.encode("utf-8")
        else:
            reference_blob = reference

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute(
            """
            INSERT INTO da_videos_reference (video_id, reference, metadata)
            VALUES (?, ?, ?)
        """,
            (video_id, reference_blob, metadata_json),
        )

        self.conn.commit()
        record_id = cursor.lastrowid
        cursor.close()

        return record_id

    def get_by_id(self, ref_id: int) -> Optional[Dict[str, Any]]:
        """
        Get reference by ID

        Args:
            ref_id: Reference ID

        Returns:
            Optional[Dict]: Reference record or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, video_id, reference, metadata, created_at
            FROM da_videos_reference
            WHERE id = ?
        """,
            (ref_id,),
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
            List[Dict]: List of reference records with decoded reference data
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, video_id, reference, metadata, created_at
            FROM da_videos_reference
            WHERE video_id = ?
            ORDER BY created_at DESC
        """,
            (video_id,),
        )

        rows = cursor.fetchall()
        cursor.close()

        return [self._row_to_dict(row) for row in rows]

    def get_reference_content(self, video_id: str) -> Optional[str]:
        """
        Get all reference content for a video as formatted text for AI prompts

        Args:
            video_id: Video identifier

        Returns:
            Optional[str]: Formatted reference content or None if no references
        """
        refs = self.get_all_by_video(video_id)

        if not refs:
            return None

        content_parts = []

        for ref in refs:
            reference_data = ref.get("reference")

            if not reference_data:
                continue

            # reference_data is already decoded to dict in _row_to_dict
            if isinstance(reference_data, dict):
                # Format search results for AI
                items = reference_data.get("items", [])
                if items:
                    #content_parts.append(f"검색 쿼리: {reference_data.get('query', '')}")
                    content_parts.append("please refer to this info. ")

                    for i, item in enumerate(items, 1):
                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        url = item.get("url", "")

                        content_parts.append(f"{i}. {title}")
                        if snippet:
                            content_parts.append(f"   {snippet}")
                        if url:
                            content_parts.append(f"   출처: {url}")
                        content_parts.append("")

        if not content_parts:
            return None

        return "\n".join(content_parts).strip()

    def update(
        self,
        ref_id: int,
        reference: Optional[Union[bytes, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update reference record

        Args:
            ref_id: Reference ID
            reference: New reference content (if provided)
            metadata: New metadata (if provided)

        Returns:
            bool: True if updated, False if not found
        """
        cursor = self.conn.cursor()

        # Build dynamic update query
        updates = []
        params = []

        if reference is not None:
            if isinstance(reference, str):
                reference_blob = reference.encode("utf-8")
            else:
                reference_blob = reference
            updates.append("reference = ?")
            params.append(reference_blob)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        params.append(ref_id)
        query = f"UPDATE da_videos_reference SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, params)
        self.conn.commit()

        updated = cursor.rowcount > 0
        cursor.close()

        return updated

    def delete(self, ref_id: int) -> bool:
        """
        Delete reference record

        Args:
            ref_id: Reference ID

        Returns:
            bool: True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM da_videos_reference
            WHERE id = ?
        """,
            (ref_id,),
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
            Dict: Row as dictionary with decoded reference and parsed metadata
        """
        data = dict(row)

        # Decode reference BLOB to dict
        if data.get("reference"):
            try:
                reference_bytes = data["reference"]
                reference_str = reference_bytes.decode("utf-8")
                data["reference"] = json.loads(reference_str)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                # If decoding fails, keep as raw bytes
                data["reference"] = data.get("reference")

        # Parse metadata JSON
        if data.get("metadata"):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                data["metadata"] = None

        return data
