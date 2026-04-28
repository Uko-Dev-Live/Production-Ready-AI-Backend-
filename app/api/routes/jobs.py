"""
app/api/routes/jobs.py
───────────────────────
AI Job routes — submit tasks and poll for results.

POST /jobs           → create a job, dispatch Celery task, return job_id
GET  /jobs           → list your jobs
GET  /jobs/{id}      → poll job status + result
GET  /jobs/{id}/raw  → get raw Celery task result (low-level debug)
"""

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.job import JobCreate, JobListOut, JobOut
from app.services.job_service import job_service
from app.workers.ai_tasks import run_ai_job
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/jobs", tags=["AI Jobs"])


@router.post(
    "",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new AI background job",
)
async def create_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an AI task for background processing.

    1. A Job row is created with status='pending'.
    2. A Celery task is dispatched to the Redis queue.
    3. The job_id is returned immediately — no waiting for the AI.
    4. Poll GET /jobs/{id} to check progress.

    Supported job_type values:
    - **summarise** — condense text into bullet points
    - **sentiment** — classify as positive/negative/neutral
    - **classify**  — assign a content category
    - **generate**  — generate new text based on a prompt
    """
    # Step 1: Create the DB record
    job = await job_service.create_job(db, user_id=current_user.id, data=payload)

    # Step 2: Dispatch the Celery task
    # .delay(job.id) is shorthand for .apply_async(args=[job.id])
    task = run_ai_job.delay(job.id)

    # Step 3: Attach the Celery UUID to the DB row for later lookup
    await job_service.attach_task_id(db, job, task_id=task.id)

    return job


@router.get("", response_model=JobListOut, summary="List your AI jobs")
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, jobs = await job_service.list_for_user(
        db, user_id=current_user.id, page=page, page_size=page_size
    )
    return JobListOut(total=total, items=jobs)


@router.get("/{job_id}", response_model=JobOut, summary="Poll job status and result")
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch the current status and result of an AI job.

    - status='pending'   → job is queued, not started yet
    - status='running'   → worker is processing it now
    - status='completed' → result field contains the AI output
    - status='failed'    → error_message field has the reason
    """
    job = await job_service.get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return job


@router.get("/{job_id}/raw", summary="Raw Celery task status (debug)")
async def get_raw_celery_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Directly query Celery's result backend for the task state.
    Useful for debugging when DB status and Celery state diverge.
    """
    job = await job_service.get_by_id(db, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job.celery_task_id:
        return {"celery_state": "UNSCHEDULED", "result": None}

    task_result = AsyncResult(job.celery_task_id, app=celery_app)
    return {
        "celery_task_id": job.celery_task_id,
        "celery_state": task_result.state,
        "result": task_result.result if task_result.ready() else None,
    }
