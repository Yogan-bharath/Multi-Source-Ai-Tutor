"""
Authentication and security services using Argon2id and JWT with HttpOnly cookies.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Request, Response, HTTPException, status, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from database import get_db, get_utc_now

settings = get_settings()
ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def create_access_token(user_id: str, email: str) -> str:
    """Generate signed JWT access token with expiration."""
    now = get_utc_now()
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "email": email.lower().strip(),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "ai-tutor-backend",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer="ai-tutor-backend",
        )
        return payload
    except (jwt.PyJWTError, Exception):
        return None

def set_auth_cookie(response: Response, token: str):
    """Set secure HttpOnly authentication cookie."""
    max_age = settings.jwt_access_token_expire_minutes * 60
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )

def clear_auth_cookie(response: Response):
    """Clear authentication cookie on logout."""
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )

def get_token_from_request(request: Request) -> Optional[str]:
    """Extract token from HttpOnly cookie or Authorization Bearer header."""
    # 1. Cookie
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        return token

    # 2. Authorization Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None

async def get_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    FastAPI dependency to authenticate requests.
    Validates token and returns user document from database.
    """
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated.",
        )

    return user

async def get_optional_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Optional[dict]:
    """Dependency that returns authenticated user if token present, otherwise None."""
    token = get_token_from_request(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    return await db.users.find_one({"_id": payload["sub"]})
