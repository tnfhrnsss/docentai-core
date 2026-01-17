"""
Images Router
Handles image upload operations
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pathlib import Path
import uuid

from database import get_db
from database.repositories import VideoRepository, ImageRepository
from config.settings import get_settings
from app.auth import get_current_session

router = APIRouter(prefix="/api/upload", tags=["Images"])


@router.post("/{video_id}")
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
