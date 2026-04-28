"""
app/db/session.py
──────────────────
Async SQLAlchemy engine and session factory.

Key concepts:
  • AsyncEngine   — manages the PostgreSQL connection pool asynchronously.
  • AsyncSession  — represents a single unit-of-work (transaction).
  • get_db()      — FastAPI dependency that yields a session per request,
                    then commits or rolls back automatically.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# The engine holds the connection pool.
# pool_pre_ping=True drops stale connections before handing them out.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,      # log SQL statements in debug mode
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory — every call produces a new AsyncSession bound to our engine
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,   # objects remain accessible after commit
    class_=AsyncSession,
)


async def get_db() -> AsyncSession:
    """
    FastAPI dependency.

    Usage in route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...

    The 'async with' context manager automatically commits on success
    and rolls back on any unhandled exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
