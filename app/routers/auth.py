"""
Authentication Router
Handles token issuance and authentication
"""
from fastapi import APIRouter, HTTPException, Header, Request
from database import get_db
from database.repositories import SessionRepository
from config.settings import get_settings
from app.auth import create_access_token
from app.utils import get_client_ip
import logging

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.post("/token")
async def issue_token(
    request: Request,
    x_profile_id: str = Header(..., alias="X-Profile-ID")
):
    """
    토큰 발급/재사용 API

    Issues or reuses a JWT access token based on the user's profile ID.
    If a valid (non-expired) token exists for the profile, it will be reused.
    Otherwise, a new token will be issued.

    Headers:
    - X-Profile-ID: User's profile identifier (e.g., Netflix MDX_PROFILEID)

    Response:
    - success: Boolean indicating success
    - token: JWT access token
    - expiresAt: Token expiration timestamp (ISO 8601)
    - sessionId: Unique session identifier
    - reused: Boolean indicating if token was reused (true) or newly issued (false)
    """
    try:
        # Get client IP
        client_ip = get_client_ip(request)

        db = get_db()
        session_repo = SessionRepository(db.connection)
        settings = get_settings()

        # Check if valid session exists for this profile_id
        existing_session = session_repo.get_valid_session_by_profile_id(x_profile_id)

        if existing_session:
            # Reuse existing session but create NEW token with updated expiration
            session_id = existing_session["session_id"]

            # IP 변경 감지 (모니터링 목적)
            existing_metadata = existing_session.get("metadata", {})
            original_ip = existing_metadata.get("client_ip", "unknown")

            if original_ip != "unknown" and original_ip != client_ip:
                # IP가 변경되었음을 WARNING 로그로 기록
                logger.warning(
                    f"IP changed for session: profile_id={x_profile_id}, "
                    f"session_id={session_id}, "
                    f"original_ip={original_ip}, "
                    f"current_ip={client_ip}"
                )

            # Create new token with extended expiration
            # Note: We generate a new JWT token to update the exp claim
            # Otherwise, the old token's exp remains outdated even if DB expires_at is extended
            # IMPORTANT: Reuse the existing session_id to maintain consistency
            token_data = create_access_token(x_profile_id, session_id=session_id)

            # Update session with new token (same session_id, new token with fresh exp)
            session_repo.update_token(session_id, token_data["token"])
            session_repo.extend_expiration(
                session_id, extend_hours=settings.JWT_EXPIRATION_DAYS * 24
            )

            # Log token refresh
            logger.info(
                f"Token refreshed: profile_id={x_profile_id}, "
                f"session_id={session_id}, client_ip={client_ip}"
            )

            return {
                "success": True,
                "token": token_data["token"],  # Return NEW token with updated exp
                "expiresAt": token_data["expires_at"],
                "sessionId": session_id,
                "reused": True,
            }

        # No valid session found - create new token
        token_data = create_access_token(x_profile_id)

        session_repo.create(
            session_id=token_data["session_id"],
            token=token_data["token"],
            metadata={
                "profile_id": x_profile_id,
                "client_ip": client_ip,
            },
            expires_in_hours=settings.JWT_EXPIRATION_DAYS * 24,
        )

        # Log new token issuance
        logger.info(
            f"New token issued: profile_id={x_profile_id}, "
            f"session_id={token_data['session_id']}, client_ip={client_ip}"
        )

        return {
            "success": True,
            "token": token_data["token"],
            "expiresAt": token_data["expires_at"],
            "sessionId": token_data["session_id"],
            "reused": False,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to issue token: {str(e)}"
        )
