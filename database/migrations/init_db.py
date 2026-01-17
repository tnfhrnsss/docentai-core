"""
Initial database schema migration
"""
import sqlite3


def create_tables(conn: sqlite3.Connection):
    """
    Create initial database tables

    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()

    # 0. 환경 테이블
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS da_settings (
             id TEXT UNIQUE NOT NULL,
             setting_value TEXT NOT NULL,
             metadata TEXT,
             created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # 1. 영상 메타데이터 테이블
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS da_videos (
            video_id TEXT UNIQUE NOT NULL,
            platform TEXT NOT NULL,
            title TEXT,
            lang TEXT DEFAULT 'ko',
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # 2. 영상 참조 정보 테이블 (나무위키, 위키피디아 등)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS da_videos_reference (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            ref_url TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES da_videos(video_id) ON DELETE CASCADE,
            UNIQUE(id, video_id)
        )
    """
    )

    # 인덱스 생성
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reference_video_id
        ON da_videos_reference(video_id)
    """
    )

    # 3. 사용자 세션 정보 테이블
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS da_session (
            session_id TEXT UNIQUE NOT NULL,
            token TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT
        )
    """
    )

    # 인덱스 생성
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_session_expires
        ON da_session(expires_at)
    """
    )

    # 4. 이미지 메타정보 테이블 (GCS 업로드된 스크린샷)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS da_images (
            image_id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            depot_path TEXT NOT NULL,
            file_size INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES da_videos(video_id) ON DELETE CASCADE
        )
    """
    )

    # 인덱스 생성
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_images_video
        ON da_images(video_id)
    """
    )

    # 5. 요청 테이블
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS da_record (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            image_id TEXT,
            session_id TEXT NOT NULL,
            created_at DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # 인덱스 생성
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_record_session
        ON da_record(session_id)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_record_video
        ON da_record(video_id)
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_record_image
            ON da_record(image_id)
        """
    )

    conn.commit()
    cursor.close()

    print("✅ All tables created successfully")


def drop_tables(conn: sqlite3.Connection):
    """
    Drop all tables (for testing or reset)

    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()

    tables = [
        "da_images",
        "da_videos_reference",
        "da_session",
        "da_videos",
        "da_record",
        "da_settings",
    ]

    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()
    cursor.close()

    print("✅ All tables dropped successfully")


def check_tables_exist(conn: sqlite3.Connection) -> dict:
    """
    Check if all required tables exist

    Args:
        conn: SQLite database connection

    Returns:
        dict: Table name to existence status mapping
    """
    cursor = conn.cursor()

    tables = [
        "da_images",
        "da_videos_reference",
        "da_session",
        "da_videos",
        "da_record",
        "da_settings",
    ]

    results = {}
    for table in tables:
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=?
        """,
            (table,),
        )
        results[table] = cursor.fetchone() is not None

    cursor.close()
    return results


if __name__ == "__main__":
    # 테스트용 코드
    import sys
    from pathlib import Path

    # Add project root to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from database.connection import get_db

    db = get_db()

    print("Creating tables...")
    create_tables(db.connection)

    print("\nChecking tables...")
    status = check_tables_exist(db.connection)
    for table, exists in status.items():
        print(f"  {table}: {'✅' if exists else '❌'}")

    db.close()
