"""
Image Repository
da_images 테이블에 대한 CRUD 작업을 담당합니다.
"""
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime


class ImageRepository:
    """Repository for image metadata operations"""

    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize repository with database connection

        Args:
            conn: SQLite database connection
        """
        self.conn = conn

    def create(
        self,
        image_id: str,
        video_id: str,
        depot_path: str,
        file_size: Optional[int] = None,
    ) -> str:
        """
        Create new image record

        Args:
            image_id: Unique image identifier (UUID)
            video_id: Associated video identifier
            depot_path: Physical file path where image is stored
            file_size: File size in bytes

        Returns:
            str: Created image_id

        Raises:
            sqlite3.IntegrityError: If image_id already exists or video_id doesn't exist
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO da_images (image_id, video_id, depot_path, file_size)
            VALUES (?, ?, ?, ?)
        """,
            (image_id, video_id, depot_path, file_size),
        )

        self.conn.commit()
        cursor.close()

        return image_id

    def get_by_image_id(self, image_id: str) -> Optional[Dict[str, Any]]:
        """
        Get image by image_id

        Args:
            image_id: Image identifier

        Returns:
            Optional[Dict]: Image record or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT image_id, video_id, depot_path, file_size, created_at
            FROM da_images
            WHERE image_id = ?
        """,
            (image_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return self._row_to_dict(row)
        return None

    def get_by_video_id(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Get all images associated with a video

        Args:
            video_id: Video identifier

        Returns:
            List[Dict]: List of image records
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT image_id, video_id, depot_path, file_size, created_at
            FROM da_images
            WHERE video_id = ?
            ORDER BY created_at DESC
        """,
            (video_id,),
        )

        rows = cursor.fetchall()
        cursor.close()

        return [self._row_to_dict(row) for row in rows]

    def exists(self, image_id: str) -> bool:
        """
        Check if image exists

        Args:
            image_id: Image identifier

        Returns:
            bool: True if exists, False otherwise
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT 1 FROM da_images WHERE image_id = ?
        """,
            (image_id,),
        )

        exists = cursor.fetchone() is not None
        cursor.close()

        return exists

    def delete(self, image_id: str) -> bool:
        """
        Delete image record

        Args:
            image_id: Image identifier

        Returns:
            bool: True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM da_images WHERE image_id = ?
        """,
            (image_id,),
        )

        self.conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()

        return deleted

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List all images with pagination

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[Dict]: List of image records
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT image_id, video_id, depot_path, file_size, created_at
            FROM da_images
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        rows = cursor.fetchall()
        cursor.close()

        return [self._row_to_dict(row) for row in rows]

    def count(self, video_id: Optional[str] = None) -> int:
        """
        Count total images

        Args:
            video_id: Filter by video_id (optional)

        Returns:
            int: Total count
        """
        cursor = self.conn.cursor()

        if video_id:
            cursor.execute(
                """
                SELECT COUNT(*) FROM da_images WHERE video_id = ?
            """,
                (video_id,),
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM da_images")

        count = cursor.fetchone()[0]
        cursor.close()

        return count

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Convert SQLite row to dictionary

        Args:
            row: SQLite row object

        Returns:
            Dict: Row as dictionary
        """
        return dict(row)
