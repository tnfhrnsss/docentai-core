"""
Authentication utilities for JWT token management
"""
import jwt
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, Depends
from config.settings import get_settings
from database import get_db
from database.repositories import SessionRepository


def create_access_token(profile_id: str) -> Dict[str, Any]:
    """
    Create JWT access token for a profile

    Args:
        profile_id: User's profile identifier (e.g., MDX_PROFILEID)

    Returns:
        Dict containing:
        - token: JWT token string
        - session_id: Unique session identifier
        - expires_at: Token expiration timestamp
    """
    settings = get_settings()

    # Generate unique session ID
    session_id = str(uuid.uuid4())

    # Calculate expiration time
    expires_delta = timedelta(days=settings.JWT_EXPIRATION_DAYS)
    expires_at = datetime.utcnow() + expires_delta

    # Create JWT payload
    payload = {
        "session_id": session_id,
        "profile_id": profile_id,
        "exp": expires_at,
        "iat": datetime.utcnow(),
        "type": "access"
    }

    # Encode JWT
    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    return {
        "token": token,
        "session_id": session_id,
        "profile_id": profile_id,
        "expires_at": expires_at.isoformat() + "Z"
    }


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token

    Args:
        token: JWT token string

    Returns:
        Dict: Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_session(
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Dependency to get current session from Authorization header

    Args:
        authorization: Authorization header (Bearer token)

    Returns:
        Dict: Session information containing session_id and profile_id

    Raises:
        HTTPException: If token is missing, invalid, or session not found
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )

    token = parts[1]

    # Verify JWT token
    payload = verify_token(token)

    # Verify session exists in database
    db = get_db()
    session_repo = SessionRepository(db.connection)
    session = session_repo.get_valid_session(payload["session_id"])

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Session not found or expired"
        )

    return {
        "session_id": payload["session_id"],
        "profile_id": payload["profile_id"],
        "session_data": session
    }


def get_optional_session(
    authorization: Optional[str] = Header(None)
) -> Optional[Dict[str, Any]]:
    """
    Dependency to optionally get current session (doesn't raise if missing)

    Args:
        authorization: Authorization header (Bearer token)

    Returns:
        Optional[Dict]: Session information or None if not authenticated
    """
    try:
        if not authorization:
            return None

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token = parts[1]
        payload = verify_token(token)

        db = get_db()
        session_repo = SessionRepository(db.connection)
        session = session_repo.get_valid_session(payload["session_id"])

        if not session:
            return None

        return {
            "session_id": payload["session_id"],
            "profile_id": payload["profile_id"],
            "session_data": session
        }
    except Exception:
        return None
