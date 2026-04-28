"""
app/api/deps.py
────────────────
FastAPI dependency functions — reusable auth + DB helpers.

A "dependency" in FastAPI is a function you inject into route handlers
with Depends(). FastAPI calls it automatically before your route runs.

get_current_user:
  1. Reads the Authorization header
  2. Decodes the JWT
  3. Looks up the user in the DB
  4. Returns the User object OR raises HTTP 401
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.user_service import user_service

# HTTPBearer extracts the "Bearer <token>" from the Authorization header
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the JWT and return the authenticated User.
    Raises HTTP 401 if the token is missing, expired, or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await user_service.get_by_id(db, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception

    return user
