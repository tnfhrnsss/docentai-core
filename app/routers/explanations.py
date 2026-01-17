"""
Explanations Router
Handles AI-powered subtitle explanation
"""
from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
import time

from database import get_db
from database.repositories import (
    VideoRepository,
    ImageRepository,
    SettingsRepository,
    RequestRepository,
)
from app.spec.models import (
    ExplainRequest,
    ExplainResponse,
    ExplainResponseData,
    Explanation,
    Source,
    Reference,
)
from app.auth import get_current_session
from app.client.gemini import get_gemini_client

router = APIRouter(prefix="/api/explanations", tags=["Explanations"])


@router.post("", response_model=ExplainResponse)
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

        # 0. Log request to da_request table
        request_repo = RequestRepository(db.connection)
        request_id = request_repo.create(
            video_id=request.videoId,
            session_id=session["session_id"],
            image_id=request.imageId,
            lang=request.language,
        )

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
