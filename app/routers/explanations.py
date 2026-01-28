"""
Explanations Router
Handles AI-powered subtitle explanation
"""
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from google.api_core import exceptions as google_exceptions

from app.auth import get_current_session
from app.client.gemini import get_gemini_client
from app.spec.models import (
    ExplainRequest,
    ExplainResponse,
    ExplainResponseData,
    Explanation,
    Source,
    Reference,
)
from config.settings import get_settings
from database import get_db
from database.repositories import (
    VideoRepository,
    ImageRepository,
    SettingsRepository,
    RequestRepository,
    ReferenceRepository,
)

router = APIRouter(prefix="/api/explanations", tags=["Explanations"])
logger = logging.getLogger(__name__)


@router.post("/videos/{video_id}", response_model=ExplainResponse)
async def explain_subtitle(
    video_id: str,
    request: ExplainRequest,
    session: dict = Depends(get_current_session)
):
    """
    대사 맥락 분석 API

    Authentication: Required (Bearer token)

    Workflow:
    1. Load prompt template from DB
    2. Get or create video metadata (priority: DB title > request body title)
    3. Get reference data for context
    4. Get image file (if provided)
    5. Build context subtitles string
    6. Build non-verbal cues string
    7. Validate title (required for AI call)
    8. Bind variables to prompt template
    9. Call Gemini API for analysis
    10. Return explanation
    """
    start_time = time.time()

    # DEBUG 모드일 때 request body 로깅
    settings = get_settings()
    if settings.DEBUG or settings.LOG_LEVEL == "DEBUG":
        logger.debug(f"Explanation request body: {request.dict()}")

    try:
        db = get_db()

        # 0. Log request to da_request table
        request_repo = RequestRepository(db.connection)
        request_id = request_repo.create(
            video_id=video_id,
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

        # 2. Get or create video metadata
        video_repo = VideoRepository(db.connection)
        video = video_repo.get_by_video_id(video_id)

        # Determine title with priority: DB title > request body title > error
        if video:
            # Video exists - use DB data
            video_title = video.get("title") or request.title
            video_platform = video.get("platform", "unknown")
            video_metadata = video.get("metadata", {}) or {}
        else:
            # Video doesn't exist - use request body data
            video_title = request.title
            video_platform = request.platform or "unknown"
            video_metadata = request.metadata or {}

            # Create video in background if we have title
            if video_title and video_title.strip():
                try:
                    logger.info(f"Video not found, creating new video: {video_id}")
                    video_repo.create(
                        video_id=video_id,
                        platform=video_platform,
                        title=video_title,
                        metadata=request.metadata,
                    )
                    logger.info(f"Created new video: {video_id}")
                except Exception as create_error:
                    # Log error but don't fail the request
                    logger.error(f"Failed to create video {video_id}: {create_error}")

        # Extract non-null metadata fields
        metadata_context = ""
        if video_metadata:
            metadata_lines = []
            for key, value in video_metadata.items():
                if value is not None and value != "":
                    metadata_lines.append(f"- {key}: {value}")

            if metadata_lines:
                metadata_context = "\n".join(metadata_lines)

        logger.info(f"Video metadata: {video_metadata}")
        logger.info(f"Metadata context: {metadata_context}")

        # 3. Get reference data for context (if available)
        ref_repo = ReferenceRepository(db.connection)
        reference_content = ref_repo.get_reference_content(video_id)

        logger.info(f"Reference content: {reference_content}")

        # Build reference context for prompt
        if reference_content:
            reference_context = f"""
참고 정보:
{reference_content}

위 참고 정보를 활용하여 더 정확하고 상세한 설명을 제공하세요.
"""
        else:
            reference_context = ""

        # 4. Get image file path (if provided)
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

        # 5. Build context subtitles string (이전 자막 문맥)
        # 빈 값이면 섹션 자체를 제거하여 토큰 절약
        context_subtitles = ""
        if request.context and len(request.context) > 0:
            context_lines = ["## 이전 자막"]
            for ctx in request.context:
                # 비언어적 표현이 있으면 표시
                non_verbal = ""
                if ctx.nonVerbalCues and len(ctx.nonVerbalCues) > 0:
                    non_verbal = f" [{', '.join(ctx.nonVerbalCues)}]"

                context_lines.append(
                    f"[{ctx.timestamp:.1f}초] {ctx.text}{non_verbal}"
                )

            context_subtitles = "\n".join(context_lines)

        logger.info(f"Context subtitles ({len(request.context) if request.context else 0} items)")

        # 6. Build non-verbal cues string (현재 자막의 비언어적 표현)
        # 빈 값이면 섹션 자체를 제거하여 토큰 절약
        non_verbal_cues = ""
        if request.currentSubtitle and request.currentSubtitle.nonVerbalCues:
            if len(request.currentSubtitle.nonVerbalCues) > 0:
                cues_str = ", ".join(request.currentSubtitle.nonVerbalCues)
                non_verbal_cues = f"## 비언어적 표현\n{cues_str}"

        logger.info(f"Non-verbal cues: {non_verbal_cues if non_verbal_cues else 'None'}")

        # 7. Validate title before AI call (required for prompt)
        if not video_title or not video_title.strip():
            raise HTTPException(
                status_code=400,
                detail="Video title is required. Please provide title in request body or ensure video exists in database."
            )

        # 8. Bind variables to prompt template
        final_prompt = prompt_template.format(
            video_title=video_title,
            language=request.language,
            subtitle_text=request.selectedText,
            metadata_context=metadata_context,
            reference_context=reference_context,
            context_subtitles=context_subtitles,
            non_verbal_cues=non_verbal_cues,
        )

        # 9. Call Gemini API with prompt and optional image
        gemini_client = get_gemini_client()
        images = [str(image_path)] if image_path else None
        ai_response = gemini_client.generate_multimodal(
            prompt=final_prompt,
            images=images,
            temperature=0.7,
        )

        # 10. Create explanation from AI response
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
    except google_exceptions.DeadlineExceeded as e:
        logger.error(
            f"Gemini API timeout: video_id={video_id}, error={str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=504,  # Gateway Timeout
            detail="AI response timeout. Please try again."
        )
    except Exception as e:
        logger.error(
            f"Failed to generate explanation: video_id={video_id}, error={str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )
