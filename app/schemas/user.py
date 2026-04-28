"""
app/schemas/user.py
────────────────────
Pydantic v2 schemas for User API input/output validation.

Pydantic schemas are separate from SQLAlchemy models on purpose:
  • Models define HOW data is stored (database columns, relationships).
  • Schemas define WHAT data crosses the API boundary (request bodies,
    response payloads) — with strict types, validators, and docs.

Never return a raw SQLAlchemy model from a route; always use a schema.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Request Schemas (what the client sends) ───────────────────────────

class UserCreate(BaseModel):
    """Used when registering a new user (POST /users)."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    bio: str | None = Field(None, max_length=500)

    @field_validator("username")
    @classmethod
    def username_lowercase(cls, v: str) -> str:
        return v.lower()


class UserUpdate(BaseModel):
    """Used when updating a user profile (PATCH /users/{id})."""
    full_name: str | None = Field(None, max_length=255)
    bio: str | None = Field(None, max_length=500)
    avatar_url: str | None = None


class UserLogin(BaseModel):
    """Used for login (POST /auth/login)."""
    email: EmailStr
    password: str


# ── Response Schemas (what the API returns) ───────────────────────────

class UserOut(BaseModel):
    """Safe user representation — never includes hashed_password."""
    id: int
    email: EmailStr
    username: str
    full_name: str
    role: str
    bio: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime

    # model_config tells Pydantic to read attributes from ORM objects
    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    """JWT response after successful login."""
    access_token: str
    token_type: str = "bearer"


class UserListOut(BaseModel):
    """Paginated list of users."""
    total: int
    page: int
    page_size: int
    items: list[UserOut]
