"""
Database test script
데이터베이스 연결 및 CRUD 작업을 테스트합니다.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database import init_db, get_db, close_db
from database.repositories import VideoRepository, ReferenceRepository, SessionRepository


def test_video_operations():
    """Test video repository operations"""
    print("\n📹 Testing Video Repository...")

    db = get_db()
    video_repo = VideoRepository(db.connection)

    # Test CREATE
    print("  1. Creating video...")
    video_id = video_repo.create(
        video_id="81234567",
        platform="netflix",
        title="더킹: 영원의 군주",
        metadata={
            "season": 1,
            "episode": 14,
            "duration": 4200,
            "url": "https://www.netflix.com/watch/81234567",
        },
    )
    print(f"     ✅ Created video with ID: {video_id}")

    # Test READ
    print("  2. Reading video...")
    video = video_repo.get_by_video_id("81234567")
    if video:
        print(f"     ✅ Found: {video['title']}")
        print(f"        Platform: {video['platform']}")
        print(f"        Metadata: {video['metadata']}")
    else:
        print("     ❌ Video not found")

    # Test UPDATE
    print("  3. Updating video...")
    updated = video_repo.update(
        video_id="81234567",
        title="더킹: 영원의 군주 (Updated)",
        metadata={"season": 1, "episode": 15},
    )
    print(f"     ✅ Updated: {updated}")

    # Test READ after update
    video = video_repo.get_by_video_id("81234567")
    print(f"     New title: {video['title']}")
    print(f"     New metadata: {video['metadata']}")

    # Test LIST
    print("  4. Listing videos...")
    videos = video_repo.list_all(limit=10)
    print(f"     ✅ Found {len(videos)} video(s)")

    # Test COUNT
    count = video_repo.count()
    print(f"     Total videos: {count}")


def test_reference_operations():
    """Test reference repository operations"""
    print("\n📚 Testing Reference Repository...")

    db = get_db()
    ref_repo = ReferenceRepository(db.connection)

    # Test CREATE
    print("  1. Creating reference...")
    ref_id = ref_repo.create(
        video_id="81234567",
        source="namuwiki",
        ref_url="https://namu.wiki/w/더킹:%20영원의%20군주",
        metadata={"last_updated": "2024-01-13"},
    )
    print(f"     ✅ Created reference with ID: {ref_id}")

    # Test READ
    print("  2. Reading reference...")
    reference = ref_repo.get_by_video_and_source("81234567", "namuwiki")
    if reference:
        print(f"     ✅ Found: {reference['source']}")
        print(f"        URL: {reference['ref_url']}")
    else:
        print("     ❌ Reference not found")

    # Test GET ALL
    print("  3. Getting all references for video...")
    references = ref_repo.get_all_by_video("81234567")
    print(f"     ✅ Found {len(references)} reference(s)")


def test_session_operations():
    """Test session repository operations"""
    print("\n🔑 Testing Session Repository...")

    db = get_db()
    session_repo = SessionRepository(db.connection)

    # Test CREATE
    print("  1. Creating session...")
    session_id = session_repo.create(
        session_id="test_session_123",
        token="test_token_abc",
        metadata={"user_agent": "Test Browser", "ip": "127.0.0.1"},
        expires_in_hours=24,
    )
    print(f"     ✅ Created session with ID: {session_id}")

    # Test READ
    print("  2. Reading session...")
    session = session_repo.get_by_session_id("test_session_123")
    if session:
        print(f"     ✅ Found session")
        print(f"        Token: {session['token']}")
        print(f"        Expires at: {session['expires_at']}")
    else:
        print("     ❌ Session not found")

    # Test VALID SESSION
    print("  3. Checking if session is valid...")
    valid_session = session_repo.get_valid_session("test_session_123")
    if valid_session:
        print(f"     ✅ Session is valid")
    else:
        print(f"     ❌ Session expired or not found")

    # Test COUNT
    print("  4. Counting active sessions...")
    count = session_repo.count_active_sessions()
    print(f"     Total active sessions: {count}")


def cleanup():
    """Clean up test data"""
    print("\n🧹 Cleaning up test data...")

    db = get_db()
    video_repo = VideoRepository(db.connection)
    ref_repo = ReferenceRepository(db.connection)
    session_repo = SessionRepository(db.connection)

    # Delete test data
    video_repo.delete("81234567")
    session_repo.delete("test_session_123")

    print("     ✅ Cleanup complete")


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("🚀 Starting Database Tests")
        print("=" * 60)

        # Initialize database
        init_db()

        # Run tests
        test_video_operations()
        test_reference_operations()
        test_session_operations()

        # Cleanup
        cleanup()

        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Close database connection
        close_db()
