import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


class TaskTemplateCreate(BaseModel):
    restaurant_id: uuid.UUID | None = Field(default=None, description="Outlet restaurant ID (defaults to TenantContext)")
    category_id: uuid.UUID = Field(description="Task category ID")
    name: str = Field(min_length=2, max_length=200, description="Task template display name")
    code: str = Field(min_length=2, max_length=80, description="Unique template code identifier per outlet")
    description: str | None = Field(default=None, description="Detailed instructions or description")
    frequency_type: str = Field(default="DAILY", description="Scheduling frequency (e.g. DAILY, SHIFT_START, SHIFT_END, WEEKLY)")
    configuration_jsonb: dict[str, Any] = Field(description="Task rule configuration, numerical bounds, evidence requirements")

    @field_validator("code")
    @classmethod
    def validate_code_format(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Template code cannot be empty.")
        return cleaned


class TaskTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None)
    frequency_type: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)
    configuration_jsonb: dict[str, Any] | None = Field(default=None, description="Updating configuration creates a new version_number + 1")


class VersionCreateRequest(BaseModel):
    configuration_jsonb: dict[str, Any] = Field(description="Task rule configuration snapshot for new immutable version")


class TaskTemplateVersionResponse(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    version_number: int
    configuration_jsonb: dict[str, Any]
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskTemplateResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    code: str
    description: str | None
    frequency_type: str
    is_active: bool
    latest_version_number: int
    latest_version: TaskTemplateVersionResponse | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
