"""
Video Reference Collection Background Task
영상 참조 정보를 비동기로 수집하여 저장하는 백그라운드 작업
"""
import json
import logging
from datetime import datetime

from app.client.google_search import get_google_search_client
from database import get_db
from database.repositories.reference_repository import ReferenceRepository

logger = logging.getLogger(__name__)


def fetch_and_store_video_reference(video_id: str, title: str, platform: str) -> None:
    """
    영상 제목으로 참조 정보를 검색하여 da_videos_reference에 저장

    이 함수는 백그라운드 태스크로 실행되며, 실패해도 메인 API에 영향을 주지 않습니다.

    Args:
        video_id: 영상 ID
        title: 영상 제목

    Returns:
        None
    """
    try:
        logger.info(f"비디오 참조 정보 수집 시작: video_id={video_id}, title={title}")

        # 데이터베이스 연결
        db = get_db()

        # 이미 참조 데이터가 있는지 확인 (중복 방지)
        ref_repo = ReferenceRepository(db.connection)
        existing_refs = ref_repo.get_all_by_video(video_id)

        if existing_refs:
            logger.info(f"이미 참조 데이터가 존재합니다: video_id={video_id}, count={len(existing_refs)}")
            return

        # 검색 쿼리 생성 (단순화하여 검색 결과 개선)
        # Netflix의 경우 video_id로 검색, 그 외는 제목 + 플랫폼으로 검색
        if platform.lower() == "netflix":
            query_template = f"{platform} {video_id}"
        else:
            query_template = f"{title} {platform} 줄거리"

        # Google Search API 클라이언트 초기화 및 검색
        try:
            search_client = get_google_search_client()
            search_results = search_client.search_video_by_title(
                title=title,
                query_template=query_template,
                num_results=5,
            )

            logger.info(
                f"검색 완료: video_id={video_id}, "
                f"query={search_results['query']}, "
                f"results_count={len(search_results['items'])}"
            )

        except ValueError as e:
            # API 키 또는 엔진 ID가 설정되지 않은 경우
            logger.error(
                f"Google Search API 설정 오류: {e}. "
                "GOOGLE_SEARCH_API_KEY와 GOOGLE_SEARCH_ENGINE_ID를 .env에 추가하세요."
            )
            return

        except Exception as e:
            logger.error(f"Google Search API 호출 실패: video_id={video_id}, error={e}")
            return

        # 검색 결과가 없으면 종료
        if not search_results.get("items"):
            logger.warning(f"검색 결과가 없습니다: video_id={video_id}, query={search_results['query']}")
            return

        # 검색 결과를 JSON으로 직렬화하여 BLOB에 저장
        reference_data = {
            "query": search_results["query"],
            "timestamp": datetime.utcnow().isoformat(),
            "total_results": search_results["total_results"],
            "items": search_results["items"],
        }

        reference_blob = json.dumps(reference_data, ensure_ascii=False).encode("utf-8")

        # 참조 데이터 저장
        ref_id = ref_repo.create(
            video_id=video_id,
            reference=reference_blob,
            metadata={
                "source": "google_search",
                "api_version": "v1",
                "query": search_results["query"],
                "results_count": len(search_results["items"]),
            },
        )

        logger.info(
            f"참조 데이터 저장 완료: video_id={video_id}, ref_id={ref_id}, "
            f"size={len(reference_blob)} bytes"
        )

    except Exception as e:
        # 예상치 못한 오류는 로그만 남기고 계속 진행 (메인 API에 영향 없음)
        logger.error(
            f"비디오 참조 정보 수집 중 예상치 못한 오류: "
            f"video_id={video_id}, error={e}",
            exc_info=True,
        )
