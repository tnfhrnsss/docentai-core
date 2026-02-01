"""
Database connection management
SQLite 연결 및 세션 관리를 담당합니다.
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional

from config.settings import get_settings, load_database_config, ensure_data_directory


class DatabaseConnection:
    """SQLite database connection manager"""

    def __init__(self):
        self.settings = get_settings()
        self.db_config = load_database_config()
        self._connection: Optional[sqlite3.Connection] = None

    @property
    def connection(self) -> sqlite3.Connection:
        """
        Get or create database connection

        Returns:
            sqlite3.Connection: Database connection
        """
        if self._connection is None:
            self._connection = self._create_connection()
        return self._connection

    def _create_connection(self) -> sqlite3.Connection:
        """
        Create new SQLite connection with proper settings

        Returns:
            sqlite3.Connection: New database connection
        """
        # Ensure data directory exists
        ensure_data_directory()

        db_path = self.settings.DATABASE_PATH
        db_settings = self.db_config.get("database", {})

        # Create connection
        conn = sqlite3.connect(
            db_path,
            check_same_thread=db_settings.get("check_same_thread", False),
            timeout=db_settings.get("timeout", 30),
        )

        # Enable row factory for dict-like access
        conn.row_factory = sqlite3.Row

        # Enable foreign keys
        if db_settings.get("foreign_keys", True):
            conn.execute("PRAGMA foreign_keys = ON")

        # Set journal mode (WAL for better concurrency)
        journal_mode = db_settings.get("journal_mode", "WAL")
        conn.execute(f"PRAGMA journal_mode = {journal_mode}")

        return conn

    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def commit(self):
        """Commit current transaction"""
        if self._connection:
            self._connection.commit()

    def rollback(self):
        """Rollback current transaction"""
        if self._connection:
            self._connection.rollback()


# Global database connection instance
_db_connection: Optional[DatabaseConnection] = None


def get_db() -> DatabaseConnection:
    """
    Get global database connection instance

    Returns:
        DatabaseConnection: Database connection manager
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager for database cursor with automatic commit/rollback

    Yields:
        sqlite3.Cursor: Database cursor

    Example:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM da_videos")
            results = cursor.fetchall()
    """
    db = get_db()
    cursor = db.connection.cursor()
    try:
        yield cursor
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        cursor.close()


def init_db():
    """
    Initialize database connection and run migrations

    This should be called when the application starts.
    """
    from database.migrations.init_db import create_tables

    db = get_db()
    print(f"Initializing database at: {db.settings.DATABASE_PATH}")
    create_tables(db.connection)
    print("Database initialized successfully")


def close_db():
    """
    Close database connection

    This should be called when the application shuts down.
    """
    global _db_connection
    if _db_connection:
        _db_connection.close()
        _db_connection = None
        print("Database connection closed")
