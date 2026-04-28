"""
app/services/job_service.py
────────────────────────────
Business logic for creating and tracking background AI jobs.

Flow:
  1. Route calls job_service.create_job() → writes a DB row with status="pending"
  2. Route dispatches the Celery task → gets back a task_id
  3. Route calls job_service.attach_task_id() → links DB row to Celery task
  4. Client polls GET /jobs/{id} to check progress
  5. Celery worker calls job_service.mark_running/completed/failed() as it runs
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.schemas.job import JobCreate


class JobService:

    async def create_job(self, db: AsyncSession, user_id: int, data: JobCreate) -> Job:
        """Insert a new job row with status='pending'."""
        job = Job(
            user_id=user_id,
            job_type=data.job_type,
            input_data=data.input_data,
            status="pending",
        )
        db.add(job)
        await db.flush()
        await db.refresh(job)
        return job

    async def attach_task_id(self, db: AsyncSession, job: Job, task_id: str) -> Job:
        """Store the Celery task UUID on the job row after dispatching."""
        job.celery_task_id = task_id
        await db.flush()
        return job

    async def get_by_id(self, db: AsyncSession, job_id: int) -> Job | None:
        result = await db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list_for_user(
        self, db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[int, list[Job]]:
        offset = (page - 1) * page_size
        total = (
            await db.execute(
                select(func.count()).select_from(Job).where(Job.user_id == user_id)
            )
        ).scalar_one()
        jobs = (
            await db.execute(
                select(Job)
                .where(Job.user_id == user_id)
                .offset(offset)
                .limit(page_size)
                .order_by(Job.created_at.desc())
            )
        ).scalars().all()
        return total, list(jobs)

    # ── Status transitions (called by Celery worker) ───────────

    async def mark_running(self, db: AsyncSession, job_id: int) -> None:
        job = await self.get_by_id(db, job_id)
        if job:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.flush()

    async def mark_completed(self, db: AsyncSession, job_id: int, result: dict) -> None:
        job = await self.get_by_id(db, job_id)
        if job:
            job.status = "completed"
            job.result = result
            job.completed_at = datetime.now(timezone.utc)
            await db.flush()

    async def mark_failed(self, db: AsyncSession, job_id: int, error: str) -> None:
        job = await self.get_by_id(db, job_id)
        if job:
            job.status = "failed"
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
            await db.flush()


job_service = JobService()
