from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from pathlib import Path
from app.spec.models import (
    VideoCreateRequest,
    VideoResponse,
    VideoData,
    ExplainRequest,
    ExplainResponse,
    ExplainResponseData,
    Explanation,
    Source,
    Reference,
    ErrorResponse,
    ErrorDetail,
)
import time

# Import database modules
from database import init_db, close_db, get_db
from database.repositories import VideoRepository, ImageRepository

# Import settings
from config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI
    Handles startup and shutdown events
    """
    # Startup: Initialize database
    print("🚀 Starting Docent AI Core API...")
    init_db()

    # Ensure upload directory exists
    settings = get_settings()
    upload_path = Path(settings.IMAGE_UPLOAD_PATH)
    upload_path.mkdir(parents=True, exist_ok=True)
    print(f"📁 Upload directory ready: {upload_path}")

    yield
    # Shutdown: Close database connection
    print("👋 Shutting down Docent AI Core API...")
    close_db()


app = FastAPI(
    title="Docent AI Core API",
    description="Subtitle Context Explainer - Backend API (MVP)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "service": "Docent AI Core API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/upload/{video_id}")
async def upload_image(video_id: str, image: UploadFile = File(...)):
    """
    이미지 업로드 API

    Receives an image file via FormData and saves it to the configured upload directory.
    Stores image metadata in da_images table.
    Returns a unique image ID that can be used for subsequent explanation API calls.

    Path Parameters:
    - video_id: Video identifier to associate the image with

    Request:
    - image: Image file (multipart/form-data)

    Response:
    - success: Boolean indicating upload success
    - imageId: Unique identifier for the uploaded image
    - filename: Original filename
    - size: File size in bytes
    """
    try:
        settings = get_settings()
        upload_path = Path(settings.IMAGE_UPLOAD_PATH)

        # Verify video exists
        db = get_db()
        video_repo = VideoRepository(db.connection)
        if not video_repo.exists(video_id):
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

        # Generate unique image ID
        image_id = str(uuid.uuid4())
        file_extension = Path(image.filename).suffix if image.filename else ".jpg"
        filename = f"{image_id}{file_extension}"
        file_path = upload_path / filename

        # Save uploaded file
        content = await image.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Save image metadata to database
        image_repo = ImageRepository(db.connection)
        image_repo.create(
            image_id=image_id,
            video_id=video_id,
            depot_path=str(file_path),
            file_size=len(content),
        )

        return {
            "success": True,
            "imageId": image_id,
            "filename": image.filename,
            "size": len(content),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/api/videos", response_model=VideoResponse, status_code=201)
async def create_video_metadata(request: VideoCreateRequest):
    """
    영상 메타정보 저장 API

    Creates or updates video metadata in SQLite database.

    Workflow:
    1. Check if video already exists
    2. If exists, update metadata
    3. If not, create new record
    """
    from datetime import datetime
    import sqlite3

    db = get_db()
    video_repo = VideoRepository(db.connection)

    # Prepare metadata
    metadata = {
        "platform": request.platform,
        "title": request.title,
        "lang": request.lang,
        "season": request.season,
        "episode": request.episode,
    }

    try:
        # Check if video already exists
        existing = video_repo.get_by_video_id(request.videoId)

        if existing:
            # Update existing video
            video_repo.update(
                video_id=request.videoId, title=request.title, metadata=metadata
            )
            current_time = existing["created_at"]
            updated_time = datetime.utcnow().isoformat() + "Z"
        else:
            # Create new video
            video_repo.create(
                video_id=request.videoId,
                platform=request.platform,
                title=request.title,
                metadata=metadata,
            )
            current_time = datetime.utcnow().isoformat() + "Z"
            updated_time = current_time

        video_data = VideoData(
            videoId=request.videoId,
            platform=request.platform,
            title=request.title,
            season=request.season,
            episode=request.episode,
            duration=request.duration,
            url=request.url,
            createdAt=current_time,
            updatedAt=updated_time,
        )

        return VideoResponse(success=True, data=video_data)

    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Video conflict: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/api/explanations", response_model=ExplainResponse)
async def explain_subtitle(request: ExplainRequest):
    """
    대사 맥락 분석 API - MVP 더미 버전

    실제 구현 시:
    1. Redis 캐시 확인
    2. Vector DB에서 유사 세그먼트 검색
    3. PostgreSQL에서 엔티티 및 참조 정보 조회
    4. Gemini API로 설명 생성
    5. 결과 캐싱
    """
    start_time = time.time()

    dummy_explanation = Explanation(
        text=f"'{request.selectedText}'는 {request.timestamp:.1f}초 시점의 중요한 대사입니다. "
        f"이 부분은 등장인물 간의 관계를 이해하는 데 핵심적인 장면이에요. "
        f"앞선 {int(request.timestamp - 120)}초 부근에서 언급된 사건과 연결되어 있습니다.",
        sources=[
            Source(
                type="video_analysis",
                title=f"{request.metadata.get('title', '영상')} 자막 분석",
            ),
            Source(
                type="namuwiki",
                title=f"{request.metadata.get('title', '작품')} 등장인물",
                url="https://namu.wiki/w/example",
            ),
        ],
        references=[
            Reference(
                timestamp=request.timestamp - 120,
                description=f"{int((request.timestamp - 120) / 60)}분 {int((request.timestamp - 120) % 60)}초 - 관련 장면",
            ),
            Reference(
                timestamp=request.timestamp - 300,
                description=f"{int((request.timestamp - 300) / 60)}분 {int((request.timestamp - 300) % 60)}초 - 배경 설명",
            ),
        ],
    )

    response_time = int((time.time() - start_time) * 1000)

    return ExplainResponse(
        success=True,
        data=ExplainResponseData(
            explanation=dummy_explanation,
            cached=False,
            responseTime=response_time,
        ),
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
