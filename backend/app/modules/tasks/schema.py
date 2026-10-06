import uuid
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field


class TaskGenerateRequest(BaseModel):
    restaurant_id: uuid.UUID | None = Field(default=None, description="Outlet restaurant ID (defaults to TenantContext)")
    target_date: date | None = Field(default=None, description="Target date for generating recurring tasks (YYYY-MM-DD)")


class TaskGenerateResult(BaseModel):
    restaurant_id: uuid.UUID
    target_date: str
    templates_processed: int
    tasks_created: int
    tasks_skipped_existing: int
    task_ids: list[uuid.UUID]


class TaskAssignmentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    assigned_at: datetime

    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    template_id: uuid.UUID
    template_version_id: uuid.UUID
    occurrence_key: str
    status: str
    due_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    assignments: list[TaskAssignmentResponse] = []

    class Config:
        from_attributes = True
