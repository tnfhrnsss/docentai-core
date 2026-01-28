"""
Video Reference Collection Background Task
영상 참조 정보를 비동기로 수집하여 저장하는 백그라운드 작업

2단계 구조 (검색 강제):
1. Gemini + Google Search tool로 검색만 강제 수행 (출처 수집)
2. 검색 결과를 videos_reference 테이블에 저장
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from google.api_core import exceptions as google_exceptions

from app.client.gemini import GeminiClient
from database import get_db
from database.repositories.reference_repository import ReferenceRepository

logger = logging.getLogger(__name__)

# Search instruction 파일 경로
SEARCH_INSTRUCTION_PATH = Path(__file__).parent.parent.parent / "config/prompts/search_instruction.txt"


def fetch_and_store_video_reference(video_id: str, title: str, platform: str) -> None:
    """
    Gemini + Google Search를 사용하여 영상 참조 정보를 검색 후 저장

    2단계 구조 중 1단계 (검색 강제):
    - Gemini에 google_search tool을 붙여서 검색만 강제 수행
    - 검색 결과(제목, URL)를 da_videos_reference에 저장
    - 출처가 없으면 저장하지 않음

    이 함수는 백그라운드 태스크로 실행되며, 실패해도 메인 API에 영향을 주지 않습니다.

    Args:
        video_id: 영상 ID
        title: 영상 제목
        platform: 플랫폼 이름

    Returns:
        None
    """
    try:
        logger.info(f"[STEP 1] 비디오 참조 정보 검색 시작: video_id={video_id}, title={title}")

        # 데이터베이스 연결
        db = get_db()

        # 이미 참조 데이터가 있는지 확인 (중복 방지)
        ref_repo = ReferenceRepository(db.connection)
        existing_refs = ref_repo.get_all_by_video(video_id)

        if existing_refs:
            logger.info(f"이미 참조 데이터가 존재합니다: video_id={video_id}, count={len(existing_refs)}")
            return

        # 검색 쿼리 생성
        if title and title not in ["넷플릭스", "netflix", "유튜브", "youtube"]:
            # 유효한 제목이 있는 경우
            search_query = f"{platform} {title} 줄거리 등장인물 배경"
        elif platform.lower() == "netflix":
            search_query = f"{platform} {video_id} plot characters"
        else:
            search_query = f"{title} {platform} 줄거리"

        logger.info(f"검색 쿼리: {search_query}")

        # Gemini 클라이언트 생성 (grounding 활성화)
        try:
            gemini_client = GeminiClient(enable_grounding=True)
        except ValueError as e:
            logger.error(f"Gemini API 키 설정 오류: {e}. .env에 GEMINI_API_KEY를 추가하세요.")
            return

        # 검색 instruction 로드
        system_instruction = ""  # 초기화
        try:
            with open(SEARCH_INSTRUCTION_PATH, "r", encoding="utf-8") as f:
                system_instruction = f.read()
        except FileNotFoundError:
            logger.error(f"Search instruction file not found: {SEARCH_INSTRUCTION_PATH}")
            # Fallback to default instruction
            system_instruction = """
웹 검색을 수행하고, 관련 있는 결과의 제목과 URL을 나열하라.
추론이나 요약은 하지 마라.
"""

        # Gemini API 호출 (검색만 수행)
        search_prompt = f"""
{system_instruction}

다음 주제에 대해 웹 검색을 수행하라:

{search_query}

관련 있는 검색 결과의 제목과 URL을 나열하라.
"""

        try:
            # generate_multimodal_with_grounding 사용 (grounding 활성화된 모델)
            result = gemini_client.generate_multimodal_with_grounding(
                prompt=search_prompt,
                temperature=0.3,  # 낮은 temperature로 일관된 포맷 유지
            )

            logger.info(f"Gemini 응답 길이: {len(result['text'])} characters")

            # grounding_metadata 확인
            web_sources = []
            search_queries_used = []

            if result.get("grounding_metadata"):
                # 정상 경로: grounding metadata 파싱
                parsed = GeminiClient.parse_grounding_metadata(result["grounding_metadata"])
                web_sources = parsed.get("web_sources", [])
                search_queries_used = parsed.get("search_queries", [])
                logger.info(f"Grounding metadata 파싱: {len(web_sources)}개 출처")

            elif result.get("web_sources_from_text"):
                # Fallback: text에서 추출한 URL 사용
                web_sources = result["web_sources_from_text"]
                logger.info(f"Fallback - text에서 추출: {len(web_sources)}개 출처")

            if not web_sources:
                logger.warning(f"검색 결과 없음 (출처 없음): video_id={video_id}")
                # 출처가 없으면 저장하지 않음
                return

            logger.info(
                f"검색 완료: video_id={video_id}, "
                f"sources_count={len(web_sources)}, "
                f"queries={search_queries_used}"
            )

            # 검색 결과를 저장 형식으로 변환
            reference_data = {
                "query": search_query,
                "timestamp": datetime.now().isoformat(),
                "search_queries": search_queries_used,  # Gemini가 사용한 검색 쿼리
                "items": [
                    {
                        "title": source.get("title", ""),
                        "url": source.get("uri", ""),
                        "snippet": source.get("snippet", ""),
                    }
                    for i, source in enumerate(web_sources)
                    if i < 3
                ],
            }

            reference_blob = json.dumps(reference_data, ensure_ascii=False).encode("utf-8")

            # metadata에 출처 방식 표시
            metadata_source = "gemini_grounding" if result.get("grounding_metadata") else "gemini_text_fallback"

            # 참조 데이터 저장
            ref_id = ref_repo.create(
                video_id=video_id,
                reference=reference_blob,
                metadata={
                    "source": metadata_source,
                    "api_version": "v2",
                    "query": search_query,
                    "results_count": len(web_sources),
                    "search_queries": search_queries_used,
                },
            )

            logger.info(
                f"[STEP 1] 참조 데이터 저장 완료: video_id={video_id}, ref_id={ref_id}, "
                f"sources={len(web_sources)}, size={len(reference_blob)} bytes, method={metadata_source}"
            )

        except google_exceptions.DeadlineExceeded as e:
            # Timeout은 경고로만 처리 (백그라운드 작업이므로 실패해도 괜찮음)
            logger.warning(
                f"Gemini 검색 timeout (정상): video_id={video_id}, error={e}. "
                "참조 데이터 없이 계속 진행합니다."
            )
            return

        except Exception as e:
            logger.error(f"Gemini 검색 실패: video_id={video_id}, error={e}", exc_info=True)
            return

    except Exception as e:
        # 예상치 못한 오류는 로그만 남기고 계속 진행 (메인 API에 영향 없음)
        logger.error(
            f"비디오 참조 정보 수집 중 예상치 못한 오류: "
            f"video_id={video_id}, error={e}",
            exc_info=True,
        )
