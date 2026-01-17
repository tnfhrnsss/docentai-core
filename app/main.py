from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
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
    SettingUpdateRequest,
)
import time

# Import database modules
from database import init_db, close_db, get_db
from database.repositories import (
    VideoRepository,
    ImageRepository,
    SessionRepository,
    SettingsRepository,
)

# Import settings
from config.settings import get_settings

# Import auth utilities
from app.auth import create_access_token, get_current_session

# Import Gemini client
from app.client.gemini import get_gemini_client


def init_prompts():
    """Initialize prompt templates in database"""
    db = get_db()
    settings_repo = SettingsRepository(db.connection)

    # Load explain prompt from file
    prompt_file = Path(__file__).parent.parent / "config" / "prompts" / "explain_prompt.txt"

    if prompt_file.exists():
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt_content = f.read()

        # Upsert prompt to database
        settings_repo.upsert(
            setting_id="explain_prompt",
            setting_value=prompt_content,
            metadata={"description": "Prompt template for explanation API", "version": "1.0"},
        )
        print("✅ Prompt templates initialized")
    else:
        print("⚠️  Warning: explain_prompt.txt not found")


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

    # Initialize prompts
    init_prompts()

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


@app.post("/api/auth/token")
async def issue_token(x_profile_id: str = Header(..., alias="X-Profile-ID")):
    """
    토큰 발급 API

    Issues a JWT access token based on the user's profile ID.
    The token should be included in subsequent API requests via Authorization header.

    Headers:
    - X-Profile-ID: User's profile identifier (e.g., Netflix MDX_PROFILEID)

    Response:
    - success: Boolean indicating success
    - token: JWT access token
    - expiresAt: Token expiration timestamp (ISO 8601)
    - sessionId: Unique session identifier
    """
    try:
        # Create JWT token
        token_data = create_access_token(x_profile_id)

        # Save session to database
        db = get_db()
        session_repo = SessionRepository(db.connection)

        settings = get_settings()
        session_repo.create(
            session_id=token_data["session_id"],
            token=token_data["token"],
            metadata={"profile_id": x_profile_id},
            expires_in_hours=settings.JWT_EXPIRATION_DAYS * 24,
        )

        return {
            "success": True,
            "token": token_data["token"],
            "expiresAt": token_data["expires_at"],
            "sessionId": token_data["session_id"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to issue token: {str(e)}"
        )


@app.post("/api/upload/{video_id}")
async def upload_image(
    video_id: str,
    image: UploadFile = File(...),
    session: dict = Depends(get_current_session)
):
    """
    이미지 업로드 API

    Receives an image file via FormData and saves it to the configured upload directory.
    Stores image metadata in da_images table.
    Returns a unique image ID that can be used for subsequent explanation API calls.

    Authentication: Required (Bearer token)

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
async def create_video_metadata(
    request: VideoCreateRequest,
    session: dict = Depends(get_current_session)
):
    """
    영상 메타정보 저장 API

    Creates or updates video metadata in SQLite database.

    Authentication: Required (Bearer token)

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
async def explain_subtitle(
    request: ExplainRequest,
    session: dict = Depends(get_current_session)
):
    """
    대사 맥락 분석 API

    Authentication: Required (Bearer token)

    Workflow:
    1. Load prompt template from DB
    2. Get image file and encode to base64
    3. Get video metadata
    4. Bind variables to prompt template
    5. Call Gemini API for analysis
    6. Return explanation
    """
    start_time = time.time()

    try:
        db = get_db()

        # 1. Load prompt template from DB
        settings_repo = SettingsRepository(db.connection)
        prompt_template = settings_repo.get_value("explain_prompt")

        if not prompt_template:
            raise HTTPException(
                status_code=500,
                detail="Prompt template not found. Please check da_settings table."
            )

        # 2. Get video metadata
        video_repo = VideoRepository(db.connection)
        video = video_repo.get_by_video_id(request.videoId)

        if not video:
            raise HTTPException(status_code=404, detail=f"Video not found: {request.videoId}")

        video_title = video.get("title", "Unknown")

        # 3. Get image file path (if provided)
        image_path = None
        if request.imageId:
            image_repo = ImageRepository(db.connection)
            image = image_repo.get_by_image_id(request.imageId)

            if not image:
                raise HTTPException(status_code=404, detail=f"Image not found: {request.imageId}")

            image_path = Path(image["depot_path"])

            if not image_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Image file not found at: {image_path}"
                )

        # 4. Bind variables to prompt template
        final_prompt = prompt_template.format(
            video_title=video_title,
            language=request.language,
            subtitle_text=request.selectedText,
        )

        # 5. Call Gemini API with prompt and optional image
        gemini_client = get_gemini_client()
        images = [str(image_path)] if image_path else None
        ai_response = gemini_client.generate_multimodal(
            prompt=final_prompt,
            images=images,
            temperature=0.7,
        )

        # 7. Create explanation from AI response
        explanation = Explanation(
            text=ai_response,
            sources=[
                Source(
                    type="ai_analysis",
                    title="Gemini AI 분석",
                ),
                Source(
                    type="video_context",
                    title=f"{video_title} - {request.timestamp:.1f}초",
                ),
            ],
            references=[],  # Can be populated from AI response if needed
        )

        response_time = int((time.time() - start_time) * 1000)

        return ExplainResponse(
            success=True,
            data=ExplainResponseData(
                explanation=explanation,
                cached=False,
                responseTime=response_time,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )


@app.get("/api/settings/{setting_id}")
async def get_setting(setting_id: str, session: dict = Depends(get_current_session)):
    """
    설정 조회 API

    Authentication: Required (Bearer token)

    Path Parameters:
    - setting_id: Setting identifier (e.g., 'explain_prompt')

    Response:
    - success: Boolean
    - data: Setting record with id, value, metadata, created_at
    """
    try:
        db = get_db()
        settings_repo = SettingsRepository(db.connection)

        setting = settings_repo.get_by_id(setting_id)

        if not setting:
            raise HTTPException(status_code=404, detail=f"Setting not found: {setting_id}")

        return {
            "success": True,
            "data": setting
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get setting: {str(e)}")


@app.put("/api/settings/{setting_id}")
async def update_setting(
    setting_id: str,
    request: SettingUpdateRequest,
    session: dict = Depends(get_current_session)
):
    """
    설정 업데이트 API

    Authentication: Required (Bearer token)

    Path Parameters:
    - setting_id: Setting identifier (e.g., 'explain_prompt')

    Request Body:
    - settingValue: New setting value (text)

    Response:
    - success: Boolean
    - message: Success message
    """
    try:
        db = get_db()
        settings_repo = SettingsRepository(db.connection)

        # Check if setting exists
        if not settings_repo.exists(setting_id):
            raise HTTPException(status_code=404, detail=f"Setting not found: {setting_id}")

        # Update setting
        updated = settings_repo.update(
            setting_id=setting_id,
            setting_value=request.settingValue
        )

        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update setting")

        return {
            "success": True,
            "message": f"Setting '{setting_id}' updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update setting: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
