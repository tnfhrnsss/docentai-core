"""
Test script for video reference integration
Tests Google Search API, background tasks, and repository functions
"""
import sys
from pathlib import Path
import json
import time

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database import get_db
from database.repositories.reference_repository import ReferenceRepository
from database.repositories.settings_repository import SettingsRepository
from database.repositories.video_repository import VideoRepository
from app.tasks.video_reference import fetch_and_store_video_reference


def test_google_search_client():
    """Test Google Search API client"""
    print("\n" + "=" * 60)
    print("TEST 1: Google Search API Client")
    print("=" * 60)

    try:
        from app.client.google_search import get_google_search_client

        client = get_google_search_client()
        print("✅ GoogleSearchClient initialized successfully")

        # Test search
        query = "카고 넷플릭스 줄거리"
        print(f"\n🔍 Searching: {query}")

        results = client.search_video_info(query, num_results=3)

        print(f"✅ Search completed: {len(results['items'])} results")
        print(f"   Query: {results['query']}")
        print(f"   Total results: {results['total_results']}")

        if results["items"]:
            print("\n📄 Sample result:")
            first = results["items"][0]
            print(f"   Title: {first['title']}")
            print(f"   URL: {first['url']}")
            print(f"   Snippet: {first['snippet'][:100]}...")

        return True

    except ValueError as e:
        print(f"⚠️  Skipping: {e}")
        print("   (Add GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID to .env)")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reference_repository():
    """Test ReferenceRepository BLOB handling"""
    print("\n" + "=" * 60)
    print("TEST 2: ReferenceRepository BLOB Handling")
    print("=" * 60)

    try:
        db = get_db()
        ref_repo = ReferenceRepository(db.connection)

        # Create test reference data
        test_video_id = "test_video_001"
        test_data = {
            "query": "테스트 영상 줄거리",
            "timestamp": "2025-01-18T12:00:00",
            "items": [
                {
                    "title": "테스트 결과 1",
                    "url": "https://example.com/1",
                    "snippet": "이것은 테스트 스니펫입니다."
                }
            ]
        }

        # Convert to bytes
        test_blob = json.dumps(test_data, ensure_ascii=False).encode("utf-8")

        print(f"\n💾 Creating reference record for video: {test_video_id}")
        ref_id = ref_repo.create(
            video_id=test_video_id,
            reference=test_blob,
            metadata={"source": "test", "test": True}
        )

        print(f"✅ Reference created: ID={ref_id}")

        # Retrieve and verify
        print("\n🔍 Retrieving reference data...")
        refs = ref_repo.get_all_by_video(test_video_id)

        if refs:
            print(f"✅ Retrieved {len(refs)} reference(s)")
            ref = refs[0]
            print(f"   ID: {ref['id']}")
            print(f"   Video ID: {ref['video_id']}")
            print(f"   Reference type: {type(ref['reference'])}")

            if isinstance(ref['reference'], dict):
                print(f"   Query: {ref['reference'].get('query')}")
                print(f"   Items count: {len(ref['reference'].get('items', []))}")
                print("✅ BLOB correctly decoded to dict")
            else:
                print("❌ BLOB not decoded properly")
                return False

            # Test get_reference_content
            print("\n📝 Testing get_reference_content...")
            content = ref_repo.get_reference_content(test_video_id)

            if content:
                print(f"✅ Reference content generated ({len(content)} chars)")
                print("\n   Preview:")
                print("   " + content[:200].replace("\n", "\n   ") + "...")
            else:
                print("❌ Failed to generate reference content")
                return False

        else:
            print("❌ No references retrieved")
            return False

        # Cleanup
        print(f"\n🧹 Cleaning up test data...")
        deleted = ref_repo.delete_all_by_video(test_video_id)
        print(f"✅ Deleted {deleted} reference(s)")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_background_task():
    """Test background task integration"""
    print("\n" + "=" * 60)
    print("TEST 3: Background Task Integration")
    print("=" * 60)

    try:
        db = get_db()
        video_repo = VideoRepository(db.connection)
        ref_repo = ReferenceRepository(db.connection)

        # Create test video
        test_video_id = "test_cargo_movie"
        test_title = "카고"

        print(f"\n💾 Creating test video: {test_title}")
        try:
            video_repo.create(
                video_id=test_video_id,
                platform="netflix",
                title=test_title,
                metadata={"test": True}
            )
            print(f"✅ Video created: {test_video_id}")
        except Exception as e:
            # Video might already exist
            print(f"⚠️  Video might already exist: {e}")

        # Check if reference already exists
        existing_refs = ref_repo.get_all_by_video(test_video_id)
        if existing_refs:
            print(f"\n⚠️  Deleting {len(existing_refs)} existing reference(s)...")
            ref_repo.delete_all_by_video(test_video_id)

        # Run background task
        print(f"\n🚀 Running background task for: {test_title}")
        print("   (This will call Google Search API if configured)")

        fetch_and_store_video_reference(test_video_id, test_title)

        # Wait a moment for async operations
        time.sleep(1)

        # Check if reference was created
        print("\n🔍 Checking for created references...")
        refs = ref_repo.get_all_by_video(test_video_id)

        if refs:
            print(f"✅ Background task created {len(refs)} reference(s)")

            ref = refs[0]
            if isinstance(ref['reference'], dict):
                query = ref['reference'].get('query', '')
                items_count = len(ref['reference'].get('items', []))
                print(f"   Query: {query}")
                print(f"   Results: {items_count} items")
                print("✅ Reference data is valid")

                # Show sample content
                content = ref_repo.get_reference_content(test_video_id)
                if content:
                    print(f"\n📝 Generated reference content preview:")
                    print("   " + content[:300].replace("\n", "\n   ") + "...")

            else:
                print("❌ Reference data format is invalid")
                return False

        else:
            print("⚠️  No references created (check logs for API key configuration)")
            print("   This is expected if Google Search API is not configured.")

        # Cleanup
        print(f"\n🧹 Cleaning up test data...")
        ref_repo.delete_all_by_video(test_video_id)
        print(f"✅ Cleanup complete")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_settings():
    """Test settings configuration"""
    print("\n" + "=" * 60)
    print("TEST 4: Settings Configuration")
    print("=" * 60)

    try:
        db = get_db()
        settings_repo = SettingsRepository(db.connection)

        # Check search query template
        print("\n🔍 Checking 'video_reference_search_query' setting...")
        query_template = settings_repo.get_value("video_reference_search_query")

        if query_template:
            print(f"✅ Search query template found: {query_template}")

            if "{title}" in query_template:
                print("✅ Template contains {title} placeholder")
            else:
                print("❌ Template missing {title} placeholder")
                return False
        else:
            print("❌ Search query template not found")
            print("   Run setup_reference_settings.py first")
            return False

        # Check explain prompt
        print("\n🔍 Checking 'explain_prompt' setting...")
        explain_prompt = settings_repo.get_value("explain_prompt")

        if explain_prompt:
            print(f"✅ Explain prompt found ({len(explain_prompt)} chars)")

            if "{reference_context}" in explain_prompt:
                print("✅ Prompt contains {reference_context} placeholder")
            else:
                print("⚠️  Prompt missing {reference_context} placeholder")
                print("   Update the prompt to include reference context")
        else:
            print("❌ Explain prompt not found")
            return False

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🧪 VIDEO REFERENCE INTEGRATION TEST SUITE")
    print("=" * 60)

    results = {
        "Settings Configuration": test_settings(),
        "ReferenceRepository": test_reference_repository(),
        "Google Search Client": test_google_search_client(),
        "Background Task": test_background_task(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All tests passed!")
        print("\n📋 Next steps:")
        print("1. Make sure GOOGLE_SEARCH_API_KEY is set in .env")
        print("2. Make sure GOOGLE_SEARCH_ENGINE_ID is set in .env")
        print("3. Start the server: uvicorn app.main:app --reload")
        print("4. Test the API endpoints")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
