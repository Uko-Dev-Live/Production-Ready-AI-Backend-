"""
app/services/user_service.py
─────────────────────────────
Business logic for User operations.

Services sit between the route handlers and the database.
Routes should stay thin (validate input, call a service, return output).
All database queries and business rules live here.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:

    # ── Create ─────────────────────────────────────────────────

    async def create_user(self, db: AsyncSession, data: UserCreate) -> User:
        """Hash password and persist a new user."""
        # Check uniqueness first — give a clear error message
        if await self.get_by_email(db, data.email):
            raise ValueError(f"Email '{data.email}' is already registered.")
        if await self.get_by_username(db, data.username):
            raise ValueError(f"Username '{data.username}' is already taken.")

        user = User(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            bio=data.bio,
        )
        db.add(user)
        await db.flush()   # write to DB but don't commit yet (session.commit in get_db)
        await db.refresh(user)
        return user

    # ── Read ───────────────────────────────────────────────────

    async def get_by_id(self, db: AsyncSession, user_id: int) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> User | None:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def list_users(
        self, db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[int, list[User]]:
        """Return (total_count, page_of_users)."""
        offset = (page - 1) * page_size
        total_result = await db.execute(select(func.count()).select_from(User))
        total = total_result.scalar_one()
        users_result = await db.execute(
            select(User).offset(offset).limit(page_size).order_by(User.id)
        )
        return total, list(users_result.scalars().all())

    # ── Update ─────────────────────────────────────────────────

    async def update_user(
        self, db: AsyncSession, user: User, data: UserUpdate
    ) -> User:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        await db.flush()
        await db.refresh(user)
        return user

    # ── Auth ───────────────────────────────────────────────────

    async def authenticate(
        self, db: AsyncSession, email: str, password: str
    ) -> tuple[User, str] | None:
        """
        Verify credentials and return (user, jwt_token) or None.
        Returns None (not an exception) so the route can return 401.
        """
        user = await self.get_by_email(db, email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        token = create_access_token(subject=user.id)
        return user, token


# Single shared instance — import this everywhere instead of instantiating
user_service = UserService()
