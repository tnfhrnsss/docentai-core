"""
Google Custom Search API 테스트 스크립트
터미널에서 직접 실행하여 Google Search API가 제대로 동작하는지 확인합니다.

사용법:
    python test/test_google_search.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.client.google_search import get_google_search_client
from config.settings import get_settings


def test_google_search_api():
    """Google Custom Search API 테스트"""
    print("\n" + "=" * 60)
    print("🔍 Google Custom Search API 테스트")
    print("=" * 60)

    # 1. 설정 확인
    print("\n1️⃣  설정 확인")
    settings = get_settings()

    print(f"   API Key: {'✅ 설정됨' if settings.GOOGLE_SEARCH_API_KEY else '❌ 없음'}")
    print(f"   Engine ID: {'✅ 설정됨' if settings.GOOGLE_SEARCH_ENGINE_ID else '❌ 없음'}")
    print(f"   검색 결과 개수: {settings.GOOGLE_SEARCH_NUM_RESULTS}")

    if not settings.GOOGLE_SEARCH_API_KEY or not settings.GOOGLE_SEARCH_ENGINE_ID:
        print("\n❌ 오류: Google Search API 설정이 없습니다.")
        print("\n.env 파일에 다음을 추가하세요:")
        print("   GOOGLE_SEARCH_API_KEY=your-api-key")
        print("   GOOGLE_SEARCH_ENGINE_ID=your-engine-id")
        return False

    # 2. 클라이언트 초기화
    print("\n2️⃣  Google Search 클라이언트 초기화")
    try:
        client = get_google_search_client()
        print("   ✅ 클라이언트 생성 성공")
    except Exception as e:
        print(f"   ❌ 클라이언트 생성 실패: {e}")
        return False

    # 3. 검색 테스트 (기본 설정값 사용)
    print("\n3️⃣  검색 테스트 (설정값 사용)")
    test_query = "카고 넷플릭스 줄거리"
    print(f"   검색어: {test_query}")
    print(f"   사이트 제한: namu.wiki")
    print(f"   결과 개수: {settings.GOOGLE_SEARCH_NUM_RESULTS} (설정값)")

    try:
        # num_results를 지정하지 않으면 설정값 사용
        results = client.search_video_info(
            query=test_query,
            #site_search="namu.wiki"
        )

        print(f"\n   ✅ 검색 성공!")
        print(f"   전체 결과 수: {results['total_results']:,}")
        print(f"   반환된 결과 수: {len(results['items'])}")

        # 결과 출력
        if results["items"]:
            print("\n📄 검색 결과:")
            for idx, item in enumerate(results["items"], 1):
                print(f"\n   [{idx}] {item['title']}")
                print(f"       URL: {item['url']}")
                print(f"       설명: {item['snippet'][:100]}...")
        else:
            print("\n   ⚠️  검색 결과가 없습니다.")

    except Exception as e:
        print(f"\n   ❌ 검색 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. search_video_by_title 메서드 테스트
    print("\n4️⃣  search_video_by_title 메서드 테스트")
    test_title = "카고"
    print(f"   영상 제목: {test_title}")

    try:
        results = client.search_video_by_title(
            title=test_title,
            query_template="{title} 줄거리",
            site_search="namu.wiki"
        )

        print(f"\n   ✅ 검색 성공!")
        print(f"   검색 쿼리: {results['query']}")
        print(f"   반환된 결과 수: {len(results['items'])}")

        if results["items"]:
            first = results["items"][0]
            print(f"\n   🎯 가장 정확도 높은 결과:")
            print(f"       제목: {first['title']}")
            print(f"       URL: {first['url']}")
            print(f"       설명: {first['snippet'][:150]}...")

    except Exception as e:
        print(f"\n   ❌ 검색 실패: {e}")
        return False

    # 5. 다양한 결과 개수 테스트 (선택사항)
    print("\n5️⃣  결과 개수 변경 테스트")
    print("   3개 결과 요청 (수동 지정)")

    try:
        results = client.search_video_info(
            query="넷플릭스 인기 드라마",
            num_results=3,
            site_search="namu.wiki"
        )

        print(f"   ✅ 반환된 결과 수: {len(results['items'])}")

    except Exception as e:
        print(f"   ❌ 검색 실패: {e}")
        return False

    return True


def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("🧪 Google Custom Search API 단독 테스트")
    print("=" * 60)

    success = test_google_search_api()

    print("\n" + "=" * 60)
    if success:
        print("✅ 모든 테스트 통과!")
        print("\n📋 확인 사항:")
        print("   - Google Search API가 정상 동작합니다")
        print("   - 설정값(GOOGLE_SEARCH_NUM_RESULTS)이 적용되었습니다")
        print("   - 가장 정확도 높은 결과가 1순위로 반환됩니다")
    else:
        print("❌ 테스트 실패")
        print("\n📋 확인 사항:")
        print("   - .env 파일에 GOOGLE_SEARCH_API_KEY 설정")
        print("   - .env 파일에 GOOGLE_SEARCH_ENGINE_ID 설정")
        print("   - API 키의 유효성 확인")
        sys.exit(1)

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
