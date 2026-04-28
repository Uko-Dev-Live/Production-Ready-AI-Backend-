"""
app/models/user.py
───────────────────
SQLAlchemy ORM model for application users.

Each class attribute maps to a database column.
SQLAlchemy handles SQL generation, type mapping, and relationships.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    # Primary key — auto-incremented by PostgreSQL
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Core user fields
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Role — used for basic authorization ("user" or "admin")
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)

    # Profile
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Status flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Audit timestamps — stored in UTC
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship — one user can have many background jobs
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user", lazy="select")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
