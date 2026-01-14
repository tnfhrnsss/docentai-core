from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# Video Metadata Models
class VideoCreateRequest(BaseModel):
    videoId: str
    platform: str
    title: str
    season: Optional[int] = None
    episode: Optional[int] = None
    duration: Optional[int] = None  # seconds
    url: Optional[str] = None


class VideoData(BaseModel):
    videoId: str
    platform: str
    title: str
    season: Optional[int] = None
    episode: Optional[int] = None
    duration: Optional[int] = None
    url: Optional[str] = None
    createdAt: str
    updatedAt: str


class VideoResponse(BaseModel):
    success: bool
    data: VideoData


# Explanation Models
class ExplainRequest(BaseModel):
    videoId: str
    selectedText: str
    timestamp: float
    metadata: Optional[dict] = None


class Source(BaseModel):
    type: str
    title: str
    url: Optional[str] = None


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
