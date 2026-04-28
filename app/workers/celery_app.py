"""
app/workers/celery_app.py
──────────────────────────
Celery application factory.

Celery is a distributed task queue:
  • The API enqueues a task (fire-and-forget) and returns immediately.
  • One or more Celery worker processes pick up tasks from Redis and run them.
  • Results are stored back in Redis so the API can poll for them.

Why background workers?
  AI API calls can take 5–30 seconds. We never block an HTTP request
  for that long — we hand the work off to a worker and return a job_id.
"""

from celery import Celery
from app.core.config import settings

# Create the Celery app.
# First arg is the module name (used in task names).
# broker  = where tasks are sent (Redis queue)
# backend = where results are stored (Redis again, different DB index)
celery_app = Celery(
    "ai_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.ai_tasks",   # auto-discover these task modules
    ],
)

celery_app.conf.update(
    # Serialise task arguments as JSON (safe, human-readable)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # UTC everywhere
    timezone="UTC",
    enable_utc=True,

    # After 1 hour, expire results from Redis to save memory
    result_expires=3600,

    # Retry a task up to 3 times if the worker crashes mid-execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Route different task types to different queues (optional but useful)
    task_routes={
        "app.workers.ai_tasks.run_ai_job": {"queue": "ai"},
        "app.workers.ai_tasks.send_welcome_email": {"queue": "email"},
    },
)
