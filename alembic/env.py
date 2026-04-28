"""
alembic/env.py
───────────────
Alembic migration environment — reads DB URL from app settings.

IMPORT CHANGE:
  Now imports target_metadata from app.db.models (not app.db.base).
  app.db.models is the central model registry that safely collects all
  models without creating any circular import cycles.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

from app.core.config import settings

# Import from the model registry — this pulls in User, Job, and Base.metadata
# without any circular import risk.
from app.db.models import target_metadata

# ── Alembic Config object ─────────────────────────────────────────────
config = context.config

# Point Alembic at the real database using the SYNC DSN (psycopg2 driver).
# Alembic is a sync CLI tool — it does not need asyncpg.
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ── Offline mode ──────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ───────────────────────────────────────────────────────
def run_migrations_online() -> None:
    """Connect to the real DB and apply pending migrations."""
    # NullPool: no connection pooling — each migration run opens and closes
    # exactly one connection. Correct for a one-shot CLI tool.
    connectable = create_engine(
        settings.SYNC_DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,   # detect column type changes in autogenerate
        )
        with context.begin_transaction():
            context.run_migrations()


# ── Entry point ───────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
