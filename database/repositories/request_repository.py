"""
Request Repository
da_request 테이블에 대한 CRUD 작업을 담당합니다.
"""
import sqlite3
from typing import Optional, List, Dict, Any


class RequestRepository:
    """Repository for API request logging operations"""

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
        session_id: str,
        image_id: Optional[str] = None,
        lang: str = "ko",
    ) -> int:
        """
        Create new request record

        Args:
            video_id: Video identifier
            session_id: Session identifier from token
            image_id: Image identifier (optional)
            lang: Language code (default: 'ko')

        Returns:
            int: Created request_id

        Raises:
            sqlite3.Error: If database error occurs
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO da_request (video_id, image_id, session_id, lang)
            VALUES (?, ?, ?, ?)
        """,
            (video_id, image_id, session_id, lang),
        )

        self.conn.commit()
        request_id = cursor.lastrowid
        cursor.close()

        return request_id

    def get_by_id(self, request_id: int) -> Optional[Dict[str, Any]]:
        """
        Get request by request_id

        Args:
            request_id: Request identifier

        Returns:
            Optional[Dict]: Request record or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT request_id, video_id, image_id, session_id, lang, created_at
            FROM da_request
            WHERE request_id = ?
        """,
            (request_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return self._row_to_dict(row)
        return None

    def get_by_session(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all requests for a session

        Args:
            session_id: Session identifier
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[Dict]: List of request records
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT request_id, video_id, image_id, session_id, lang, created_at
            FROM da_request
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """,
            (session_id, limit, offset),
        )

        rows = cursor.fetchall()
        cursor.close()

        return [self._row_to_dict(row) for row in rows]

    def get_by_video(
        self, video_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all requests for a video

        Args:
            video_id: Video identifier
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[Dict]: List of request records
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT request_id, video_id, image_id, session_id, lang, created_at
            FROM da_request
            WHERE video_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """,
            (video_id, limit, offset),
        )

        rows = cursor.fetchall()
        cursor.close()

        return [self._row_to_dict(row) for row in rows]

    def count(
        self,
        video_id: Optional[str] = None,
        session_id: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> int:
        """
        Count total requests with optional filters

        Args:
            video_id: Filter by video_id (optional)
            session_id: Filter by session_id (optional)
            lang: Filter by language (optional)

        Returns:
            int: Total count
        """
        cursor = self.conn.cursor()

        # Build dynamic query
        conditions = []
        params = []

        if video_id:
            conditions.append("video_id = ?")
            params.append(video_id)

        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        if lang:
            conditions.append("lang = ?")
            params.append(lang)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT COUNT(*) FROM da_request WHERE {where_clause}"

        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        cursor.close()

        return count

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get request statistics

        Returns:
            Dict: Statistics including total requests, by language, etc.
        """
        cursor = self.conn.cursor()

        # Total requests
        cursor.execute("SELECT COUNT(*) FROM da_request")
        total = cursor.fetchone()[0]

        # Requests by language
        cursor.execute(
            """
            SELECT lang, COUNT(*) as count
            FROM da_request
            GROUP BY lang
            ORDER BY count DESC
        """
        )
        by_lang = [{"lang": row[0], "count": row[1]} for row in cursor.fetchall()]

        # Requests with/without images
        cursor.execute(
            """
            SELECT
                SUM(CASE WHEN image_id IS NOT NULL THEN 1 ELSE 0 END) as with_image,
                SUM(CASE WHEN image_id IS NULL THEN 1 ELSE 0 END) as without_image
            FROM da_request
        """
        )
        image_stats = cursor.fetchone()

        cursor.close()

        return {
            "total_requests": total,
            "by_language": by_lang,
            "with_image": image_stats[0] or 0,
            "without_image": image_stats[1] or 0,
        }

    def delete(self, request_id: int) -> bool:
        """
        Delete request record

        Args:
            request_id: Request identifier

        Returns:
            bool: True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM da_request WHERE request_id = ?
        """,
            (request_id,),
        )

        self.conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()

        return deleted

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Convert SQLite row to dictionary

        Args:
            row: SQLite row object

        Returns:
            Dict: Row as dictionary
        """
        return dict(row)
