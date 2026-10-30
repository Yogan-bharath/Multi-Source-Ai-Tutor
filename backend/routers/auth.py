"""
Authentication Router: Registration, Login, Logout, and Current User Profile.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
import pymongo.errors

from database import get_db, get_utc_now
from models import UserRegisterRequest, UserLoginRequest, UserResponse
from services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    set_auth_cookie,
    clear_auth_cookie,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: UserRegisterRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Register a new user account:
    - Normalizes email to lowercase
    - Hashes password with Argon2id
    - Enforces uniqueness via MongoDB index
    - Sets secure HttpOnly authentication cookie
    """
    email_clean = req.email.lower().strip()
    name_clean = req.name.strip()

    # Check existing email
    existing = await db.users.find_one({"email": email_clean})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user_id = str(uuid.uuid4())
    now = get_utc_now()
    user_doc = {
        "_id": user_id,
        "name": name_clean,
        "email": email_clean,
        "password_hash": hash_password(req.password),
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }

    try:
        await db.users.insert_one(user_doc)
    except pymongo.errors.DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Issue token and set cookie
    token = create_access_token(user_id, email_clean)
    set_auth_cookie(response, token)

    return UserResponse(
        _id=user_id,
        name=name_clean,
        email=email_clean,
        created_at=now,
        is_active=True,
    )

@router.post("/login", response_model=UserResponse)
async def login(
    req: UserLoginRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Authenticate user with email and password:
    - Uses generic error message to prevent account enumeration
    - Verifies Argon2id hash
    - Sets HttpOnly auth cookie
    """
    email_clean = req.email.lower().strip()
    user = await db.users.find_one({"email": email_clean})

    # Constant-time comparison / generic error
    if not user or not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact support.",
        )

    token = create_access_token(user["_id"], email_clean)
    set_auth_cookie(response, token)

    return UserResponse(
        _id=user["_id"],
        name=user["name"],
        email=user["email"],
        created_at=user["created_at"],
        is_active=user.get("is_active", True),
    )

@router.post("/logout")
async def logout(response: Response):
    """Log out by clearing authentication cookie."""
    clear_auth_cookie(response)
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return UserResponse(
        _id=current_user["_id"],
        name=current_user["name"],
        email=current_user["email"],
        created_at=current_user["created_at"],
        is_active=current_user.get("is_active", True),
    )
