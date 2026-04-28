"""
app/models/job.py
──────────────────
SQLAlchemy ORM model for background jobs.

Every time a user triggers an AI task (summarise text, analyse data, etc.)
we create a Job record. The Celery worker updates its status as it runs.

Job lifecycle:
    pending → running → completed
                      → failed
"""

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Link to the user who created this job
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Celery assigns a UUID to every task — we store it here for lookup
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    # What kind of AI task is this?
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Job lifecycle status
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )  # pending | running | completed | failed

    # Raw input the user submitted
    input_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI result — stored as JSON so we can return structured data
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Error message if the job failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<Job id={self.id} type={self.job_type!r} status={self.status!r}>"
