"""
Settings Repository
da_settings 테이블에 대한 CRUD 작업을 담당합니다.
"""
import json
import sqlite3
from typing import Optional, List, Dict, Any


class SettingsRepository:
    """Repository for application settings operations"""

    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize repository with database connection

        Args:
            conn: SQLite database connection
        """
        self.conn = conn

    def create(
        self,
        setting_id: str,
        setting_value: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Create new setting record

        Args:
            setting_id: Setting identifier (e.g., 'explain_prompt')
            setting_value: Setting value (e.g., prompt template)
            metadata: Additional metadata as dictionary

        Returns:
            int: Created record ID

        Raises:
            sqlite3.IntegrityError: If setting_id already exists
        """
        cursor = self.conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute(
            """
            INSERT INTO da_settings (id, setting_value, metadata)
            VALUES (?, ?, ?)
        """,
            (setting_id, setting_value, metadata_json),
        )

        self.conn.commit()
        record_id = cursor.lastrowid
        cursor.close()

        return record_id

    def get_by_id(self, setting_id: str) -> Optional[Dict[str, Any]]:
        """
        Get setting by ID

        Args:
            setting_id: Setting identifier

        Returns:
            Optional[Dict]: Setting record or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, setting_value, metadata, created_at
            FROM da_settings
            WHERE id = ?
        """,
            (setting_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return self._row_to_dict(row)
        return None

    def get_value(self, setting_id: str) -> Optional[str]:
        """
        Get setting value directly

        Args:
            setting_id: Setting identifier

        Returns:
            Optional[str]: Setting value or None if not found
        """
        setting = self.get_by_id(setting_id)
        return setting["setting_value"] if setting else None

    def exists(self, setting_id: str) -> bool:
        """
        Check if setting exists

        Args:
            setting_id: Setting identifier

        Returns:
            bool: True if exists, False otherwise
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT 1 FROM da_settings WHERE id = ?
        """,
            (setting_id,),
        )

        exists = cursor.fetchone() is not None
        cursor.close()

        return exists

    def update(
        self,
        setting_id: str,
        setting_value: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update setting record

        Args:
            setting_id: Setting identifier
            setting_value: New value (if provided)
            metadata: New metadata (if provided)

        Returns:
            bool: True if updated, False if not found
        """
        cursor = self.conn.cursor()

        # Build dynamic update query
        updates = []
        params = []

        if setting_value is not None:
            updates.append("setting_value = ?")
            params.append(setting_value)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        params.append(setting_id)
        query = f"UPDATE da_settings SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, params)
        self.conn.commit()

        updated = cursor.rowcount > 0
        cursor.close()

        return updated

    def upsert(
        self,
        setting_id: str,
        setting_value: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create or update setting (INSERT OR REPLACE)

        Args:
            setting_id: Setting identifier
            setting_value: Setting value
            metadata: Metadata dictionary

        Returns:
            bool: True if successful
        """
        cursor = self.conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute(
            """
            INSERT OR REPLACE INTO da_settings (id, setting_value, metadata, created_at)
            VALUES (?, ?, ?, COALESCE((SELECT created_at FROM da_settings WHERE id = ?), CURRENT_TIMESTAMP))
        """,
            (setting_id, setting_value, metadata_json, setting_id),
        )

        self.conn.commit()
        cursor.close()

        return True

    def delete(self, setting_id: str) -> bool:
        """
        Delete setting record

        Args:
            setting_id: Setting identifier

        Returns:
            bool: True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM da_settings WHERE id = ?
        """,
            (setting_id,),
        )

        self.conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()

        return deleted

    def list_all(self) -> List[Dict[str, Any]]:
        """
        List all settings

        Returns:
            List[Dict]: List of all setting records
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, setting_value, metadata, created_at
            FROM da_settings
            ORDER BY id
        """
        )

        rows = cursor.fetchall()
        cursor.close()

        return [self._row_to_dict(row) for row in rows]

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
