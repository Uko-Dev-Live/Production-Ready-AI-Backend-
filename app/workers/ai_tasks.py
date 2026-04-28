"""
app/workers/ai_tasks.py
────────────────────────
Celery task definitions — the actual background work.

Each function decorated with @celery_app.task IS a task.
When the API calls .delay() or .apply_async() on a task, Celery
serialises the arguments and drops them on a Redis queue.
The worker picks up the message, deserialises the args, and calls the function.

IMPORTANT: Tasks run in a separate process from FastAPI.
  • No FastAPI request context exists here.
  • We create our own DB sessions using a synchronous engine.
  • We catch ALL exceptions so the job is always marked as failed (not stuck).
"""

import asyncio
import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job import Job
from app.workers.celery_app import celery_app
from app.workers.ai_engine import AIEngine

logger = structlog.get_logger(__name__)

# Synchronous engine for use inside Celery tasks
# (Celery workers don't run an asyncio event loop by default)
sync_engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True)


def _get_sync_session() -> Session:
    return Session(sync_engine)


# ── Main AI Job Task ─────────────────────────────────────────────────

@celery_app.task(
    name="app.workers.ai_tasks.run_ai_job",
    bind=True,               # 'self' gives access to task metadata (task_id, retry)
    max_retries=3,
    default_retry_delay=10,  # seconds between retries
)
def run_ai_job(self, job_id: int) -> dict:
    """
    Process an AI job by type and store the result in the database.

    Supported job types:
      • summarise  — condense a block of text
      • sentiment  — classify positive / negative / neutral
      • classify   — categorise content into predefined labels
      • generate   — free-form text generation
    """
    log = logger.bind(task_id=self.request.id, job_id=job_id)
    log.info("Task started")

    with _get_sync_session() as db:
        # 1. Load the job
        job: Job | None = db.execute(
            select(Job).where(Job.id == job_id)
        ).scalar_one_or_none()

        if not job:
            log.error("Job not found")
            return {"error": "Job not found"}

        # 2. Mark as running
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            # 3. Dispatch to the correct AI handler
            engine = AIEngine()
            result = engine.run(job_type=job.job_type, input_text=job.input_data or "")

            # 4. Store result
            job.status = "completed"
            job.result = result
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

            log.info("Task completed", job_type=job.job_type)
            return result

        except Exception as exc:
            log.error("Task failed", error=str(exc))
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

            # Retry if we have attempts left
            raise self.retry(exc=exc)


# ── Email Notification Task ──────────────────────────────────────────

@celery_app.task(name="app.workers.ai_tasks.send_welcome_email")
def send_welcome_email(user_email: str, username: str) -> dict:
    """
    Simulate sending a welcome email after user registration.

    In production: replace with boto3 SES, SendGrid, or Mailgun calls.
    """
    logger.info("Sending welcome email", email=user_email)

    # Simulate network delay of an email provider
    import time
    time.sleep(1)

    message = (
        f"Hello {username}, welcome to AI Backend! "
        "Your account is ready. Explore the API at /docs."
    )
    logger.info("Welcome email sent", email=user_email)
    return {"sent_to": user_email, "message": message, "status": "sent"}


# ── Scheduled Health-Check Task ──────────────────────────────────────

@celery_app.task(name="app.workers.ai_tasks.health_check")
def health_check() -> dict:
    """
    Periodic task to verify workers are alive.
    Configure in Celery Beat for cron-like scheduling.
    """
    now = datetime.now(timezone.utc).isoformat()
    logger.info("Health check ping", timestamp=now)
    return {"status": "ok", "timestamp": now}
