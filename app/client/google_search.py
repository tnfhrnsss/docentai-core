"""
Google Custom Search API Client
영상 관련 참조 정보를 수집하기 위한 Google Custom Search API 클라이언트
"""
import logging
from typing import Optional, List, Dict, Any
import urllib.parse
import urllib.request
import json

from config.settings import get_settings

logger = logging.getLogger(__name__)


class GoogleSearchClient:
    """
    Google Custom Search API 클라이언트

    영상 제목을 기반으로 관련 정보(줄거리, 등장인물, 배경)를 검색합니다.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        engine_id: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """
        Google Search 클라이언트 초기화

        Args:
            api_key: Google Search API 키. 없으면 설정에서 로드
            engine_id: Custom Search Engine ID. 없으면 설정에서 로드
            api_url: API URL. 없으면 설정에서 로드
        """
        settings = get_settings()
        self.api_key = api_key or settings.GOOGLE_SEARCH_API_KEY
        self.engine_id = engine_id or settings.GOOGLE_SEARCH_ENGINE_ID
        self.api_url = api_url or settings.GOOGLE_SEARCH_API_URL

        if not self.api_key:
            raise ValueError(
                "GOOGLE_SEARCH_API_KEY가 설정되지 않았습니다. "
                ".env 파일에 GOOGLE_SEARCH_API_KEY를 추가하세요."
            )

        if not self.engine_id:
            raise ValueError(
                "GOOGLE_SEARCH_ENGINE_ID가 설정되지 않았습니다. "
                ".env 파일에 GOOGLE_SEARCH_ENGINE_ID를 추가하세요."
            )

    def search_video_info(
        self,
        query: str,
        num_results: int = 5,
    ) -> Dict[str, Any]:
        """
        영상 관련 정보 검색

        Args:
            query: 검색 쿼리 (예: "카고 넷플릭스 줄거리 등장인물 배경")
            num_results: 반환할 결과 개수 (최대 10)

        Returns:
            검색 결과 딕셔너리
            {
                "query": str,
                "total_results": int,
                "items": [
                    {
                        "title": str,
                        "url": str,
                        "snippet": str
                    },
                    ...
                ]
            }

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            # URL 파라미터 구성
            params = {
                "key": self.api_key,
                "cx": self.engine_id,
                "q": query,
                "num": min(num_results, 10),  # 최대 10개
            }

            # URL 생성
            url = f"{self.api_url}?{urllib.parse.urlencode(params)}"

            # API 호출
            logger.info(f"Google Search API 호출: query={query}, num={num_results}")

            req = urllib.request.Request(url)
            req.add_header("User-Agent", "DocentAI/1.0")

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            # 응답 파싱
            items = []
            for item in data.get("items", []):
                items.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })

            result = {
                "query": query,
                "total_results": int(data.get("searchInformation", {}).get("totalResults", 0)),
                "items": items,
            }

            logger.info(f"검색 완료: {len(items)}개 결과 반환")
            return result

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            logger.error(f"Google Search API HTTPError: {e.code} - {error_body}")
            raise Exception(f"Google Search API 호출 실패: HTTP {e.code}")

        except urllib.error.URLError as e:
            logger.error(f"Google Search API URLError: {e.reason}")
            raise Exception(f"Google Search API 연결 실패: {e.reason}")

        except json.JSONDecodeError as e:
            logger.error(f"Google Search API 응답 파싱 실패: {e}")
            raise Exception("Google Search API 응답을 파싱할 수 없습니다")

        except Exception as e:
            logger.error(f"Google Search API 예상치 못한 오류: {e}")
            raise

    def search_video_by_title(
        self,
        title: str,
        query_template: str = "{title} 넷플릭스 줄거리 등장인물 배경",
        num_results: int = 5,
    ) -> Dict[str, Any]:
        """
        영상 제목으로 관련 정보 검색

        Args:
            title: 영상 제목
            query_template: 검색 쿼리 템플릿 ({title} 자리표시자 사용)
            num_results: 반환할 결과 개수

        Returns:
            검색 결과 딕셔너리
        """
        query = query_template.format(title=title)
        return self.search_video_info(query, num_results)


# 싱글톤 인스턴스 생성 헬퍼
_search_client_instance: Optional[GoogleSearchClient] = None


def get_google_search_client() -> GoogleSearchClient:
    """
    Google Search 클라이언트 싱글톤 인스턴스 반환

    Returns:
        GoogleSearchClient 인스턴스
    """
    global _search_client_instance

    if _search_client_instance is None:
        _search_client_instance = GoogleSearchClient()

    return _search_client_instance
