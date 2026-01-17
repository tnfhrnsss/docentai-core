"""
Statistics Router
Handles statistics and analytics
"""
from fastapi import APIRouter, HTTPException, Depends

from database import get_db
from database.repositories import RequestRepository
from app.auth import get_current_session

router = APIRouter(prefix="/api/statistics", tags=["Statistics"])


@router.get("/requests")
async def get_request_statistics(session: dict = Depends(get_current_session)):
    """
    요청 통계 조회 API

    Authentication: Required (Bearer token)

    Response:
    - success: Boolean
    - data: Statistics object with total requests, by language, with/without images
    """
    try:
        db = get_db()
        request_repo = RequestRepository(db.connection)

        stats = request_repo.get_statistics()

        return {
            "success": True,
            "data": stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")
