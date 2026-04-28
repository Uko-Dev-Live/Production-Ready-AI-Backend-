"""
app/api/routes/auth.py
───────────────────────
Authentication routes: register and login.

POST /auth/register  → create account, fire welcome email task
POST /auth/login     → verify credentials, return JWT
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.user import UserCreate, UserLogin, UserOut, TokenOut
from app.services.user_service import user_service
from app.workers.ai_tasks import send_welcome_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account.

    - Validates email format and password length via Pydantic.
    - Hashes the password before storing (bcrypt).
    - Fires a background welcome-email task via Celery.
    """
    try:
        user = await user_service.create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    # Fire-and-forget: send welcome email asynchronously
    # .delay() puts the task on the Redis queue and returns immediately
    send_welcome_email.delay(user.email, user.username)

    return user


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Login and receive a JWT access token",
)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with email + password.
    Returns a Bearer JWT token valid for 24 hours.
    """
    result = await user_service.authenticate(db, payload.email, payload.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _user, token = result
    return TokenOut(access_token=token)
