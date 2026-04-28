"""
app/db/models.py
─────────────────
Central model registry — imported ONLY by Alembic's env.py.

This file's sole job is to import every SQLAlchemy model so that
Base.metadata knows about all tables when Alembic runs autogenerate.

WHY A SEPARATE FILE?
  We cannot import models inside db/base.py (circular import).
  We cannot import them inside each model file (they already import Base).
  So we collect them here in a file that nothing else in the app imports.

HOW TO ADD A NEW MODEL:
  1. Create app/models/your_model.py  (inherit from Base)
  2. Add one import line below:
         from app.models.your_model import YourModel  # noqa: F401

That is all Alembic needs to detect the new table in autogenerate.
"""

# ── Import every model here ───────────────────────────────────────────
# noqa: F401  →  tells linters "yes, this import is intentional even
#                though the name is never used directly in this file"

from app.models.user import User   # noqa: F401
from app.models.job import Job     # noqa: F401

# ── Re-export Base.metadata for alembic/env.py ───────────────────────
from app.db.base import Base

# Convenience alias used in alembic/env.py:
#   from app.db.models import target_metadata
target_metadata = Base.metadata
