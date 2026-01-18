"""
Gemini API Client
Google Gemini 멀티모달 API를 호출하는 클라이언트
"""
import os
from typing import Optional, List, Dict, Any, Union, AsyncGenerator
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
from PIL import Image
import io
import base64

from config.settings import get_settings


class GeminiClient:
    """
    Google Gemini API 클라이언트

    멀티모달 입력 (텍스트, 이미지)을 처리하고 응답을 생성합니다.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        Gemini 클라이언트 초기화

        Args:
            api_key: Gemini API 키. 없으면 설정에서 로드
            model_name: 사용할 모델 이름. 없으면 설정에서 로드
        """
        settings = get_settings()
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL_NAME

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY가 설정되지 않았습니다. "
                ".env 파일에 GEMINI_API_KEY를 추가하세요."
            )

        # Configure Gemini API
        genai.configure(api_key=self.api_key)

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
        )

        return response.text

    def generate_multimodal(
        self,
        prompt: str,
        images: Optional[List[Union[str, bytes, Image.Image]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        멀티모달 입력으로 텍스트 생성 (텍스트 + 이미지)

        Args:
            prompt: 입력 프롬프트
            images: 이미지 리스트 (파일 경로, bytes, PIL Image)
            temperature: 생성 온도
            max_tokens: 최대 토큰 수

        Returns:
            생성된 텍스트
        """
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

        response = self.model.generate_content(
            content,
            generation_config=generation_config,
        )

        return response.text


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
        )

        return response.text, chat.history

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
