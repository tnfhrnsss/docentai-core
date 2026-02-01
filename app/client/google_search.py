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
        num_results: Optional[int] = None,
        site_search: Optional[str] = None,
        site_search_filter: str = "i",
    ) -> Dict[str, Any]:
        """
        영상 관련 정보 검색

        Args:
            query: 검색 쿼리 (예: "카고 넷플릭스 줄거리 등장인물 배경")
            num_results: 반환할 결과 개수 (기본값: 설정값 사용, 최대 10)
            site_search: 특정 사이트로 검색 제한 (예: "namu.wiki")
            site_search_filter: "i" (포함) 또는 "e" (제외)

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
            # num_results가 지정되지 않으면 설정값 사용
            if num_results is None:
                settings = get_settings()
                num_results = settings.GOOGLE_SEARCH_NUM_RESULTS

            # URL 파라미터 구성
            params = {
                "key": self.api_key,
                "cx": self.engine_id,
                "q": query,
                "num": min(num_results, 10),  # 최대 10개
            }

            # 특정 사이트 검색 제한
            if site_search:
                params["siteSearch"] = site_search
                params["siteSearchFilter"] = site_search_filter

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
            logger.info(f"검색어: {query}")
            logger.info(f"검색 결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
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
        query_template: str = "{title}",
        num_results: Optional[int] = None,
        site_search: Optional[str] = "",
    ) -> Dict[str, Any]:
        """
        영상 제목으로 관련 정보 검색

        Args:
            title: 영상 제목
            query_template: 검색 쿼리 템플릿 ({title} 자리표시자 사용)
            num_results: 반환할 결과 개수 (기본값: 설정값 사용)
            site_search: 특정 사이트로 검색 제한 (기본값: "namu.wiki")

        Returns:
            검색 결과 딕셔너리
        """
        query = query_template.format(title=title)
        return self.search_video_info(query, num_results, site_search=site_search)


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
