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


class TaskEntryCreateRequest(BaseModel):
    value_numeric: float | None = Field(default=None, description="Numeric measurement value (e.g. temperature)")
    value_text: str | None = Field(default=None, description="Text observation or notes")
    value_jsonb: Any | None = Field(default=None, description="Structured checklist or custom JSON data")
    unit: str | None = Field(default=None, description="Measurement unit (e.g. C, F, %)")
    equipment_id: uuid.UUID | None = Field(default=None, description="Bound equipment entity ID")
    evidence_file_id: uuid.UUID | None = Field(default=None, description="Associated evidence file ID from presigned upload flow")
    notes: str | None = Field(default=None, description="Optional staff execution comments")


class EntryResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    equipment_id: uuid.UUID | None = None
    evidence_file_id: uuid.UUID | None = None
    idempotency_key_id: uuid.UUID | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    value_jsonb: Any | None = None
    unit: str | None = None
    safety_status: str = "NORMAL"
    recorded_at: datetime
    created_at: datetime
    task_status: str = "COMPLETED"

    class Config:
        from_attributes = True

