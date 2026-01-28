"""
Gemini API Client
Google Gemini 멀티모달 API를 호출하는 클라이언트
"""
import os
import logging
import re
from typing import Optional, List, Dict, Any, Union, AsyncGenerator
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
from PIL import Image
import io
import base64

from config.settings import get_settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Google Gemini API 클라이언트

    멀티모달 입력 (텍스트, 이미지)을 처리하고 응답을 생성합니다.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        enable_grounding: bool = False,
        timeout: Optional[int] = None,
    ):
        """
        Gemini 클라이언트 초기화

        Args:
            api_key: Gemini API 키. 없으면 설정에서 로드
            model_name: 사용할 모델 이름. 없으면 설정에서 로드
            enable_grounding: Google Search Grounding 활성화 여부
            timeout: API 호출 timeout (초). 없으면 설정에서 로드
        """
        settings = get_settings()
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL_NAME
        self.enable_grounding = enable_grounding
        self.timeout = timeout or settings.GEMINI_TIMEOUT_SECONDS

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY가 설정되지 않았습니다. "
                ".env 파일에 GEMINI_API_KEY를 추가하세요."
            )

        # Configure Gemini API
        genai.configure(api_key=self.api_key)

        # Create model with or without grounding
        if self.enable_grounding:
            logger.info("Google Search Grounding이 활성화된 모델 생성")
            from google.generativeai import protos
            google_search_tool = protos.Tool(google_search={})
            self.model = genai.GenerativeModel(
                self.model_name,
                tools=[google_search_tool]
            )
        else:
            self.model = genai.GenerativeModel(self.model_name)

    def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> str:
        """
        텍스트 생성

        Args:
            prompt: 입력 프롬프트
            temperature: 생성 온도 (0.0 ~ 1.0)
            max_tokens: 최대 토큰 수
            top_p: Nucleus sampling 파라미터
            top_k: Top-k sampling 파라미터

        Returns:
            생성된 텍스트
        """
        generation_config = {
            "temperature": temperature,
        }

        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        if top_p:
            generation_config["top_p"] = top_p
        if top_k:
            generation_config["top_k"] = top_k

        response = self.model.generate_content(
            prompt,
            generation_config=generation_config,
            request_options={"timeout": self.timeout},
        )

        # 텍스트 추출
        try:
            return response.text
        except ValueError as e:
            logger.warning(f"Multi-part response in generate_text: {e}")
            # parts에서 텍스트 추출
            text_parts = []
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
            result = ''.join(text_parts)
            if not result:
                raise ValueError("응답에서 텍스트를 추출할 수 없습니다")
            return result

    def generate_multimodal(
        self,
        prompt: str,
        images: Optional[List[Union[str, bytes, Image.Image]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        use_grounding: bool = False,
    ) -> str:
        """
        멀티모달 입력으로 텍스트 생성 (텍스트 + 이미지)

        Args:
            prompt: 입력 프롬프트
            images: 이미지 리스트 (파일 경로, bytes, PIL Image)
            temperature: 생성 온도
            max_tokens: 최대 토큰 수
            use_grounding: Google Search Grounding 사용 여부

        Returns:
            생성된 텍스트
        """
        logger.info(f"Gemini generate_multimodal 호출 - prompt: {prompt[:200]}..." if len(prompt) > 200 else f"Gemini generate_multimodal 호출 - prompt: {prompt}")
        logger.info(f"Gemini generate_multimodal - images count: {len(images) if images else 0}, temperature: {temperature}, max_tokens: {max_tokens}")

        generation_config = {
            "temperature": temperature,
        }

        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens

        # 입력 콘텐츠 구성
        content = [prompt]

        if images:
            for img in images:
                pil_image = self._load_image(img)
                content.append(pil_image)

        # Google Search Grounding 설정
        tools = None
        if use_grounding:
            from google.generativeai import protos
            tools = [protos.Tool(google_search={})]
            logger.info("Google Search Grounding 활성화")

        response = self.model.generate_content(
            content,
            generation_config=generation_config,
            tools=tools,
            request_options={"timeout": self.timeout},
        )

        # 응답 구조 디버깅
        logger.info(f"Gemini response candidates count: {len(response.candidates)}")
        for idx, candidate in enumerate(response.candidates):
            logger.info(f"Candidate {idx} parts count: {len(candidate.content.parts)}")
            for part_idx, part in enumerate(candidate.content.parts):
                part_type = type(part).__name__
                has_text = hasattr(part, 'text')
                logger.info(f"  Part {part_idx}: type={part_type}, has_text={has_text}")
                if has_text:
                    text_preview = part.text[:100] if len(part.text) > 100 else part.text
                    logger.info(f"    Text preview: {text_preview}")

        # 텍스트 추출
        try:
            result_text = response.text
            logger.info(f"Gemini generate_multimodal 응답 완료 (simple text) - length: {len(result_text)}")
        except ValueError as e:
            logger.warning(f"Multi-part response detected: {e}")
            # parts에서 텍스트 추출
            text_parts = []
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
            result_text = ''.join(text_parts)
            logger.info(f"Gemini generate_multimodal 응답 완료 (multi-part) - length: {len(result_text)}")

        return result_text

    def generate_multimodal_with_grounding(
        self,
        prompt: str,
        images: Optional[List[Union[str, bytes, Image.Image]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        멀티모달 입력으로 텍스트 생성 (Google Search Grounding 포함)

        주의: 이 함수를 사용하려면 GeminiClient를 enable_grounding=True로 생성해야 합니다.

        Args:
            prompt: 입력 프롬프트
            images: 이미지 리스트 (파일 경로, bytes, PIL Image)
            temperature: 생성 온도
            max_tokens: 최대 토큰 수

        Returns:
            Dict: {
                "text": 생성된 텍스트,
                "grounding_metadata": 출처 정보 (있는 경우),
                "search_queries": 사용된 검색 쿼리 목록
            }
        """
        if not self.enable_grounding:
            logger.warning("Grounding이 활성화되지 않았습니다. GeminiClient(enable_grounding=True)로 생성하세요.")

        logger.info(f"Gemini generate_multimodal_with_grounding 호출")
        logger.info(f"Images: {len(images) if images else 0}, temperature: {temperature}")

        generation_config = {
            "temperature": temperature,
        }

        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens

        # 입력 콘텐츠 구성
        content = [prompt]

        if images:
            for img in images:
                pil_image = self._load_image(img)
                content.append(pil_image)

        # 모델이 이미 grounding tools로 생성되었으므로 그냥 호출
        response = self.model.generate_content(
            content,
            generation_config=generation_config,
            request_options={"timeout": self.timeout},
        )

        # 텍스트 추출
        try:
            result_text = response.text
        except ValueError as e:
            logger.warning(f"Multi-part response detected: {e}")
            text_parts = []
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
            result_text = ''.join(text_parts)

        # Grounding metadata 추출
        grounding_metadata = None
        search_queries = []
        web_sources_from_text = []  # Fallback: text에서 추출한 출처

        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]

            # Grounding metadata 확인
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                grounding_metadata = candidate.grounding_metadata
                logger.info(f"Grounding metadata found")

                # Search entry point 추출
                if hasattr(grounding_metadata, 'search_entry_point') and grounding_metadata.search_entry_point:
                    search_entry_point = grounding_metadata.search_entry_point
                    if hasattr(search_entry_point, 'rendered_content'):
                        logger.info(f"Search entry point: {search_entry_point.rendered_content}")

                # Grounding supports (citations) 추출
                if hasattr(grounding_metadata, 'grounding_supports') and grounding_metadata.grounding_supports:
                    supports = grounding_metadata.grounding_supports
                    logger.info(f"Found {len(supports)} grounding supports")

                # Grounding chunks (실제 출처 정보) 추출
                if hasattr(grounding_metadata, 'grounding_chunks') and grounding_metadata.grounding_chunks:
                    chunks = grounding_metadata.grounding_chunks
                    logger.info(f"Found {len(chunks)} grounding chunks")

                    for idx, chunk in enumerate(chunks):
                        if hasattr(chunk, 'web') and chunk.web:
                            web_info = chunk.web
                            if hasattr(web_info, 'uri'):
                                logger.info(f"Chunk {idx} URI: {web_info.uri}")
                            if hasattr(web_info, 'title'):
                                logger.info(f"Chunk {idx} Title: {web_info.title}")

                # Web search queries 추출
                if hasattr(grounding_metadata, 'web_search_queries') and grounding_metadata.web_search_queries:
                    search_queries = list(grounding_metadata.web_search_queries)
                    logger.info(f"Search queries used: {search_queries}")

        # Fallback: grounding_metadata가 없지만 text에 URL이 포함된 경우
        if not grounding_metadata and result_text:
            logger.info("Grounding metadata 없음. text에서 URL 추출 시도...")
            web_sources_from_text = self._extract_urls_from_text(result_text)
            if web_sources_from_text:
                logger.info(f"Text에서 {len(web_sources_from_text)}개 URL 추출 성공")

        return {
            "text": result_text,
            "grounding_metadata": grounding_metadata,
            "search_queries": search_queries,
            "web_sources_from_text": web_sources_from_text,  # Fallback 출처
        }

    def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
    ) -> tuple[str, List[Dict[str, str]]]:
        """
        대화형 텍스트 생성 (히스토리 관리)

        Args:
            message: 사용자 메시지
            history: 대화 히스토리 [{"role": "user", "parts": ["..."]}]
            temperature: 생성 온도

        Returns:
            (응답 텍스트, 업데이트된 히스토리)
        """
        chat = self.model.start_chat(history=history or [])

        response = chat.send_message(
            message,
            generation_config={"temperature": temperature},
            request_options={"timeout": self.timeout},
        )

        # 텍스트 추출
        try:
            result_text = response.text
        except ValueError as e:
            logger.warning(f"Multi-part response in chat: {e}")
            text_parts = []
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
            result_text = ''.join(text_parts)
            if not result_text:
                raise ValueError("응답에서 텍스트를 추출할 수 없습니다")

        return result_text, chat.history

    def _extract_urls_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        텍스트에서 URL과 제목을 추출 (Fallback용)

        Gemini가 grounding_metadata를 반환하지 않고 text로만 검색 결과를 반환한 경우,
        텍스트를 파싱하여 URL과 제목을 추출합니다.

        예상 형식:
        1. [제목]
        URL: [링크]
        2. [제목]
        URL: [링크]

        Args:
            text: Gemini 응답 텍스트

        Returns:
            List[Dict]: [{"title": "...", "uri": "..."}]
        """
        sources = []

        # 패턴 1: "숫자. [제목]\nURL: [링크]" 형식
        pattern1 = r'(\d+)\.\s*(.+?)\s*\n\s*URL:\s*(https?://[^\s]+)'
        matches1 = re.findall(pattern1, text, re.MULTILINE)

        for match in matches1:
            num, title, url = match
            sources.append({
                "title": title.strip(),
                "uri": url.strip(),
            })

        # 패턴 2: 단순히 URL만 있는 경우 (제목 없이)
        if not sources:
            pattern2 = r'URL:\s*(https?://[^\s]+)'
            urls = re.findall(pattern2, text)
            for url in urls:
                sources.append({
                    "title": url,  # URL을 제목으로 사용
                    "uri": url.strip(),
                })

        # 패턴 3: 아무 URL이나 추출 (마지막 fallback)
        if not sources:
            pattern3 = r'https?://[^\s\)\]]+'
            urls = re.findall(pattern3, text)
            for url in urls:
                sources.append({
                    "title": url,
                    "uri": url.strip(),
                })

        return sources

    def _load_image(
        self,
        image: Union[str, bytes, Image.Image]
    ) -> Image.Image:
        """
        이미지를 PIL Image로 변환

        Args:
            image: 파일 경로, bytes, 또는 PIL Image

        Returns:
            PIL Image 객체
        """
        if isinstance(image, Image.Image):
            return image
        elif isinstance(image, str):
            # 파일 경로
            return Image.open(image)
        elif isinstance(image, bytes):
            # bytes 데이터
            return Image.open(io.BytesIO(image))
        else:
            raise ValueError(f"지원하지 않는 이미지 타입: {type(image)}")

    @staticmethod
    def parse_grounding_metadata(grounding_metadata) -> Dict[str, Any]:
        """
        Grounding metadata를 파싱하여 구조화된 데이터로 변환

        Args:
            grounding_metadata: Gemini API response의 grounding_metadata

        Returns:
            Dict: {
                "search_queries": 사용된 검색 쿼리 목록,
                "web_sources": [{
                    "uri": URL,
                    "title": 제목,
                    "snippet": 스니펫 (있는 경우)
                }],
                "search_entry_point": 검색 진입점 정보 (있는 경우)
            }
        """
        if not grounding_metadata:
            return {
                "search_queries": [],
                "web_sources": [],
                "search_entry_point": None,
            }

        result = {
            "search_queries": [],
            "web_sources": [],
            "search_entry_point": None,
        }

        # Search queries 추출
        if hasattr(grounding_metadata, 'web_search_queries') and grounding_metadata.web_search_queries:
            result["search_queries"] = list(grounding_metadata.web_search_queries)

        # Search entry point 추출
        if hasattr(grounding_metadata, 'search_entry_point') and grounding_metadata.search_entry_point:
            search_entry_point = grounding_metadata.search_entry_point
            if hasattr(search_entry_point, 'rendered_content'):
                result["search_entry_point"] = search_entry_point.rendered_content

        # Grounding chunks (실제 웹 출처) 추출
        if hasattr(grounding_metadata, 'grounding_chunks') and grounding_metadata.grounding_chunks:
            chunks = grounding_metadata.grounding_chunks

            for chunk in chunks:
                if hasattr(chunk, 'web') and chunk.web:
                    web_info = chunk.web
                    source = {}

                    if hasattr(web_info, 'uri'):
                        source["uri"] = web_info.uri
                    if hasattr(web_info, 'title'):
                        source["title"] = web_info.title

                    # snippet이 있으면 추가 (모든 chunk에 있지는 않음)
                    if hasattr(web_info, 'snippet'):
                        source["snippet"] = web_info.snippet

                    if source:
                        result["web_sources"].append(source)

        return result

    @staticmethod
    def encode_image_to_base64(image: Union[str, bytes, Image.Image]) -> str:
        """
        이미지를 base64로 인코딩

        Args:
            image: 파일 경로, bytes, 또는 PIL Image

        Returns:
            base64 인코딩된 문자열
        """
        if isinstance(image, str):
            with open(image, "rb") as f:
                image_bytes = f.read()
        elif isinstance(image, Image.Image):
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
        else:
            image_bytes = image

        return base64.b64encode(image_bytes).decode("utf-8")


# 싱글톤 인스턴스 생성 헬퍼
_client_instance: Optional[GeminiClient] = None


def get_gemini_client(model_name: Optional[str] = None) -> GeminiClient:
    """
    Gemini 클라이언트 싱글톤 인스턴스 반환

    Args:
        model_name: 사용할 모델 이름. 없으면 설정에서 로드

    Returns:
        GeminiClient 인스턴스
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = GeminiClient(model_name=model_name)

    return _client_instance
