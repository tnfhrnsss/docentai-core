from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# Video Metadata Models
class VideoCreateRequest(BaseModel):
    videoId: str
    platform: str
    title: str
    lang: Optional[str] = "en"  # Language code
    season: Optional[int] = None
    episode: Optional[int] = None
    duration: Optional[int] = None


class VideoData(BaseModel):
    videoId: str
    platform: str
    title: str
    season: Optional[int] = None
    episode: Optional[int] = None
    createdAt: str
    updatedAt: str


class VideoResponse(BaseModel):
    success: bool
    data: VideoData


# Explanation Models
class SubtitleContext(BaseModel):
    text: str
    timestamp: float
    nonVerbalCues: Optional[List[str]] = []  # 비언어적 표현 (효과음, 배경음악 등)


class CurrentSubtitle(BaseModel):
    text: str
    timestamp: float
    nonVerbalCues: Optional[List[str]] = []  # 비언어적 표현 (효과음, 배경음악 등)


class ExplainRequest(BaseModel):
    imageId: Optional[str] = None  # Image ID from upload API (optional)
    selectedText: str
    timestamp: float
    language: Optional[str] = "en"  # Default to Korean
    metadata: Optional[dict] = None

    # 이전 자막들 (문맥 - 최대 N개, 프론트 설정값에 따라 가변)
    context: Optional[List[SubtitleContext]] = []

    # 현재 설명을 요청하는 자막
    currentSubtitle: Optional[CurrentSubtitle] = None


class Source(BaseModel):
    type: str
    title: str


class Reference(BaseModel):
    timestamp: float
    description: str


class Explanation(BaseModel):
    text: str
    sources: List[Source]
    references: List[Reference]


class ExplainResponseData(BaseModel):
    explanation: Explanation
    cached: bool
    responseTime: int


class ExplainResponse(BaseModel):
    success: bool
    data: ExplainResponseData


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryAfter: Optional[int] = None


class ErrorResponse(BaseModel):
    success: bool
    error: ErrorDetail


# Settings Models
class SettingUpdateRequest(BaseModel):
    settingValue: str
