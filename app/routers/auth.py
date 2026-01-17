"""
Authentication Router
Handles token issuance and authentication
"""
from fastapi import APIRouter, HTTPException, Header
from database import get_db
from database.repositories import SessionRepository
from config.settings import get_settings
from app.auth import create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/token")
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
