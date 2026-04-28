"""
app/api/routes/users.py
────────────────────────
User management routes (requires authentication).

GET    /users          → list all users (admin)
GET    /users/me       → get own profile
GET    /users/{id}     → get a specific user
PATCH  /users/{id}     → update own profile
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserListOut, UserOut, UserUpdate
from app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut, summary="Get your own profile")
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the profile of the currently authenticated user."""
    return current_user


@router.get("", response_model=UserListOut, summary="List all users (paginated)")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),   # any authenticated user can list
):
    total, users = await user_service.list_users(db, page=page, page_size=page_size)
    return UserListOut(total=total, page=page, page_size=page_size, items=users)


@router.get("/{user_id}", response_model=UserOut, summary="Get a user by ID")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.patch("/{user_id}", response_model=UserOut, summary="Update your profile")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only the owner can update their own profile
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot update another user's profile.")
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return await user_service.update_user(db, user, payload)
