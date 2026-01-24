"""
Videos Router
Handles video metadata operations
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from datetime import datetime
import sqlite3

from database import get_db
from database.repositories import VideoRepository
from app.spec.models import VideoCreateRequest, VideoResponse, VideoData
from app.auth import get_current_session
from app.tasks import fetch_and_store_video_reference

router = APIRouter(prefix="/api/videos", tags=["Videos"])


@router.post("", response_model=VideoResponse, status_code=201)
async def create_video_metadata(
    request: VideoCreateRequest,
    background_tasks: BackgroundTasks,
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
    db = get_db()
    video_repo = VideoRepository(db.connection)

    # Prepare metadata
    metadata = {
        "platform": request.platform,
        "title": request.title,
        "lang": request.lang,
        "season": request.season,
        "episode": request.episode,
        "duration": request.duration,
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
            createdAt=current_time,
            updatedAt=updated_time,
        )

        # Trigger background task to fetch and store reference data
        # if request.title:
        #     background_tasks.add_task(
        #         fetch_and_store_video_reference,
        #         video_id=request.videoId,
        #         platform=request.platform,
        #         title=request.title
        #     )

        return VideoResponse(success=True, data=video_data)

    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Video conflict: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
