#!/usr/bin/env python3
"""
2단계 Grounding 구조 테스트

Stage 1: Video API 호출 → Gemini + Google Search로 출처 수집
Stage 2: Explanations API 호출 → 저장된 출처 기반으로 답변 생성
"""
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.tasks.video_reference import fetch_and_store_video_reference
from database import get_db
from database.repositories import ReferenceRepository


def test_stage1_reference_collection():
    """
    Stage 1: 참조 정보 수집 테스트

    Gemini + Google Search를 사용하여 검색 강제 실행
    """
    print("=" * 80)
    print("Stage 1: Reference Collection (Gemini + Google Search)")
    print("=" * 80)

    # Test data
    test_video_id = "test_duauddmlsnsehdwk"
    test_title = "여명의 눈동자"
    test_platform = "netflix"

    print(f"\n[1] Test Video Info:")
    print(f"  Video ID: {test_video_id}")
    print(f"  Title: {test_title}")
    print(f"  Platform: {test_platform}")

    # Delete existing references for clean test
    print(f"\n[2] Cleaning up existing references...")
    db = get_db()
    ref_repo = ReferenceRepository(db.connection)
    deleted = ref_repo.delete_all_by_video(test_video_id)
    if deleted > 0:
        print(f"  ✓ Deleted {deleted} existing references")
    else:
        print(f"  ✓ No existing references")

    # Stage 1: Fetch and store reference (with Gemini + Google Search)
    print(f"\n[3] Stage 1: Collecting references with Gemini + Google Search...")
    print(f"  This will:")
    print(f"    1. Create GeminiClient(enable_grounding=True)")
    print(f"    2. Force web search with google_search tool")
    print(f"    3. Parse grounding_metadata for sources")
    print(f"    4. Store in videos_reference table")
    print()

    try:
        fetch_and_store_video_reference(
            video_id=test_video_id,
            title=test_title,
            platform=test_platform
        )
        print("\n  ✓ Reference collection completed!")
    except Exception as e:
        print(f"\n  ✗ Reference collection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Verify stored data
    print(f"\n[4] Verifying stored references...")
    refs = ref_repo.get_all_by_video(test_video_id)

    if not refs:
        print(f"  ⚠️  No references found in database")
        print(f"     This might mean:")
        print(f"       - Gemini didn't use web search (no grounding_metadata)")
        print(f"       - Or search returned no results")
        return False

    print(f"  ✓ Found {len(refs)} reference(s)")

    for idx, ref in enumerate(refs, 1):
        print(f"\n  Reference {idx}:")
        print(f"    ID: {ref['id']}")
        print(f"    Created: {ref['created_at']}")

        if ref.get('metadata'):
            metadata = ref['metadata']
            print(f"    Metadata:")
            print(f"      Source: {metadata.get('source')}")
            print(f"      API Version: {metadata.get('api_version')}")
            print(f"      Query: {metadata.get('query')}")
            print(f"      Results Count: {metadata.get('results_count')}")
            print(f"      Search Queries: {metadata.get('search_queries')}")

        if ref.get('reference'):
            reference_data = ref['reference']
            if isinstance(reference_data, dict) and reference_data.get('items'):
                print(f"\n    Search Results ({len(reference_data['items'])} items):")
                for item_idx, item in enumerate(reference_data['items'], 1):
                    print(f"      {item_idx}. {item.get('title', 'No title')}")
                    print(f"         URL: {item.get('url', 'No URL')}")
                    if item.get('snippet'):
                        snippet = item['snippet'][:100] + "..." if len(item['snippet']) > 100 else item['snippet']
                        print(f"         Snippet: {snippet}")

    # Test get_reference_content (used by explanations API)
    print(f"\n[5] Testing get_reference_content (for explanations API)...")
    reference_content = ref_repo.get_reference_content(test_video_id)

    if reference_content:
        print(f"  ✓ Reference content formatted for AI:")
        print("  " + "-" * 76)
        lines = reference_content.split('\n')
        for line in lines[:15]:  # First 15 lines
            print(f"  {line}")
        if len(lines) > 15:
            print(f"  ... ({len(lines) - 15} more lines)")
        print("  " + "-" * 76)
    else:
        print(f"  ⚠️  No reference content available")

    return True


def test_stage2_explanation_with_reference():
    """
    Stage 2: 저장된 출처를 기반으로 설명 생성

    실제로는 explanations API를 호출하지만,
    여기서는 참조 데이터가 제대로 로드되는지만 확인
    """
    print("\n\n" + "=" * 80)
    print("Stage 2: Explanation Generation (Using Stored References)")
    print("=" * 80)

    test_video_id = "test_friends_s01e01"

    print(f"\n[1] Loading references for video: {test_video_id}")

    db = get_db()
    ref_repo = ReferenceRepository(db.connection)
    reference_content = ref_repo.get_reference_content(test_video_id)

    if not reference_content:
        print(f"  ⚠️  No reference content available")
        print(f"     Stage 1 must run first to collect references")
        return False

    print(f"  ✓ Reference content loaded")
    print(f"  Length: {len(reference_content)} characters")

    print(f"\n[2] How this would be used in explanations API:")
    print(f"  1. Load reference_content from DB (done above)")
    print(f"  2. Build reference_context for prompt:")

    reference_context = f"""
참고 정보:
{reference_content}

위 참고 정보를 활용하여 더 정확하고 상세한 설명을 제공하세요.
"""

    print(f"\n  Reference context preview:")
    print("  " + "-" * 76)
    lines = reference_context.split('\n')
    for line in lines[:10]:
        print(f"  {line}")
    if len(lines) > 10:
        print(f"  ... ({len(lines) - 10} more lines)")
    print("  " + "-" * 76)

    print(f"\n  3. This context is added to explain_prompt.txt")
    print(f"  4. Call gemini_client.generate_multimodal() (NOT grounding)")
    print(f"  5. Return explanation with stored references as sources")

    print(f"\n✓ Stage 2 verification complete!")
    print(f"  References are ready to be used by explanations API")

    return True


def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 80)
    print("2-Stage Grounding Architecture Test")
    print("=" * 80)
    print()
    print("Architecture:")
    print("  Stage 1 (Search): Gemini + google_search tool → videos_reference table")
    print("  Stage 2 (Answer): Stored references → Gemini (no grounding)")
    print()

    try:
        # Stage 1: Reference collection
        stage1_success = test_stage1_reference_collection()

        if not stage1_success:
            print("\n⚠️  Stage 1 failed. Skipping Stage 2.")
            print("   Note: Gemini might not use web search if it has knowledge")
            return

        # Wait a bit
        print("\n" + "=" * 80)
        print("Waiting 2 seconds before Stage 2...")
        time.sleep(2)

        # Stage 2: Explanation generation
        # stage2_success = test_stage2_explanation_with_reference()
        #
        # if stage1_success and stage2_success:
        #     print("\n" + "=" * 80)
        #     print("✅ All tests passed!")
        #     print("=" * 80)
        #     print()
        #     print("Summary:")
        #     print("  ✓ Stage 1: References collected with Gemini + Google Search")
        #     print("  ✓ Stage 2: References ready for explanations API")
        #     print()
        #     print("Next steps:")
        #     print("  1. Test with actual explanations API")
        #     print("  2. Verify prompt includes reference_context")
        #     print("  3. Check AI response uses the stored references")

    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
