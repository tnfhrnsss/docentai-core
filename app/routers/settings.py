"""
Settings Router
Handles application settings management
"""
from fastapi import APIRouter, HTTPException, Depends

from database import get_db
from database.repositories import SettingsRepository
from app.spec.models import SettingUpdateRequest
from app.auth import get_current_session

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/{setting_id}")
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


@router.put("/{setting_id}")
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
