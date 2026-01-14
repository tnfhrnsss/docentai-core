"""
Session Repository
da_session 테이블에 대한 CRUD 작업을 담당합니다.
"""
import json
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta


class SessionRepository:
    """Repository for user session operations"""

    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize repository with database connection

        Args:
            conn: SQLite database connection
        """
        self.conn = conn

    def create(
        self,
        session_id: str,
        token: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_in_hours: int = 24,
    ) -> int:
        """
        Create new session record

        Args:
            session_id: Session identifier
            token: Session token
            metadata: Additional metadata as dictionary
            expires_in_hours: Session expiration time in hours (default: 24)

        Returns:
            int: Created record ID

        Raises:
            sqlite3.IntegrityError: If session_id already exists
        """
        cursor = self.conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None
        expires_at = (
            datetime.utcnow() + timedelta(hours=expires_in_hours)
        ).isoformat() + "Z"

        cursor.execute(
            """
            INSERT INTO da_session (session_id, token, metadata, expires_at)
            VALUES (?, ?, ?, ?)
        """,
            (session_id, token, metadata_json, expires_at),
        )

        self.conn.commit()
        record_id = cursor.lastrowid
        cursor.close()

        return record_id

    def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by session_id

        Args:
            session_id: Session identifier

        Returns:
            Optional[Dict]: Session record or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, session_id, token, metadata, created_at, expires_at
            FROM da_session
            WHERE session_id = ?
        """,
            (session_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return self._row_to_dict(row)
        return None

    def get_valid_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session only if it's still valid (not expired)

        Args:
            session_id: Session identifier

        Returns:
            Optional[Dict]: Valid session record or None if not found/expired
        """
        cursor = self.conn.cursor()

        current_time = datetime.utcnow().isoformat() + "Z"

        cursor.execute(
            """
            SELECT id, session_id, token, metadata, created_at, expires_at
            FROM da_session
            WHERE session_id = ? AND expires_at > ?
        """,
            (session_id, current_time),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return self._row_to_dict(row)
        return None

    def update_token(self, session_id: str, token: str) -> bool:
        """
        Update session token

        Args:
            session_id: Session identifier
            token: New token

        Returns:
            bool: True if updated, False if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            UPDATE da_session SET token = ? WHERE session_id = ?
        """,
            (token, session_id),
        )

        self.conn.commit()
        updated = cursor.rowcount > 0
        cursor.close()

        return updated

    def extend_expiration(
        self, session_id: str, extend_hours: int = 24
    ) -> bool:
        """
        Extend session expiration time

        Args:
            session_id: Session identifier
            extend_hours: Hours to extend from now

        Returns:
            bool: True if updated, False if not found
        """
        cursor = self.conn.cursor()

        new_expires_at = (
            datetime.utcnow() + timedelta(hours=extend_hours)
        ).isoformat() + "Z"

        cursor.execute(
            """
            UPDATE da_session SET expires_at = ? WHERE session_id = ?
        """,
            (new_expires_at, session_id),
        )

        self.conn.commit()
        updated = cursor.rowcount > 0
        cursor.close()

        return updated

    def delete(self, session_id: str) -> bool:
        """
        Delete session record

        Args:
            session_id: Session identifier

        Returns:
            bool: True if deleted, False if not found
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM da_session WHERE session_id = ?
        """,
            (session_id,),
        )

        self.conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()

        return deleted

    def delete_expired_sessions(self) -> int:
        """
        Delete all expired sessions

        Returns:
            int: Number of deleted sessions
        """
        cursor = self.conn.cursor()

        current_time = datetime.utcnow().isoformat() + "Z"

        cursor.execute(
            """
            DELETE FROM da_session WHERE expires_at < ?
        """,
            (current_time,),
        )

        self.conn.commit()
        deleted_count = cursor.rowcount
        cursor.close()

        return deleted_count

    def count_active_sessions(self) -> int:
        """
        Count currently active (non-expired) sessions

        Returns:
            int: Number of active sessions
        """
        cursor = self.conn.cursor()

        current_time = datetime.utcnow().isoformat() + "Z"

        cursor.execute(
            """
            SELECT COUNT(*) FROM da_session WHERE expires_at > ?
        """,
            (current_time,),
        )

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
