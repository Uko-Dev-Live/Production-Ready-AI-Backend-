"""
app/db/base.py
───────────────
Defines ONLY the SQLAlchemy DeclarativeBase class.

WHY NO MODEL IMPORTS HERE:
  The previous version imported models at the bottom of this file so
  Alembic could discover them. That caused a circular import:

      models/user.py  →  imports Base  from  db/base.py
      db/base.py      →  imports User  from  models/user.py
                                ↑________________________↓
                                      CIRCULAR

  Python starts executing user.py, hits "from app.db.base import Base",
  switches to base.py, then base.py tries to import User — but user.py
  is still mid-execution and User does not exist yet in sys.modules.
  Result: ImportError: cannot import name 'User' from partially initialized module.

THE FIX:
  base.py defines ONLY Base — no model imports ever.
  A new file app/db/models.py imports all models for Alembic.
  alembic/env.py imports from app.db.models, not app.db.base.

  Clean one-way dependency tree (no cycles):

      db/base.py          ← defines Base only, no app imports
           ↑
      models/user.py      ← imports Base from db/base.py   (safe)
      models/job.py       ← imports Base from db/base.py   (safe)
           ↑
      db/models.py        ← imports all models  (used by Alembic only)
           ↑
      alembic/env.py      ← imports db/models.py for target_metadata
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Parent class for every SQLAlchemy model in this project."""
    pass
