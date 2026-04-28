"""
app/schemas/job.py
───────────────────
Pydantic schemas for Job / AI task API.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    """Submitted by the client to start a new AI background job."""
    job_type: str = Field(
        ...,
        description="Type of AI task: summarise | sentiment | classify | generate",
        examples=["summarise"],
    )
    input_data: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="Text or JSON payload the AI model will process.",
    )


class JobOut(BaseModel):
    """Returned to the client — includes status and result once complete."""
    id: int
    user_id: int
    celery_task_id: str | None
    job_type: str
    status: str          # pending | running | completed | failed
    input_data: str | None
    result: dict | None  # populated when status == "completed"
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobListOut(BaseModel):
    total: int
    items: list[JobOut]
