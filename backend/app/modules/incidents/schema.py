import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class CorrectiveActionResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    assigned_to: uuid.UUID | None = None
    recheck_entry_id: uuid.UUID | None = None
    evidence_file_id: uuid.UUID | None = None
    action_text: str
    notes: str | None = None
    status: str
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IncidentResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    entry_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    severity: str
    status: str
    detected_by: uuid.UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    corrective_actions: list[CorrectiveActionResponse] = []

    class Config:
        from_attributes = True


class AssignCAPARequest(BaseModel):
    assigned_to: uuid.UUID = Field(..., description="Staff user ID assigned to perform CAPA")
    action_text: str | None = Field(default=None, description="Updated or additional corrective action instructions")


class CompleteCAPARequest(BaseModel):
    value_numeric: float | None = Field(default=None, description="Re-check numeric measurement value")
    value_text: str | None = Field(default=None, description="Re-check text observation")
    value_jsonb: Any | None = Field(default=None, description="Re-check JSON observation")
    unit: str | None = Field(default=None, description="Measurement unit (e.g. C, F)")
    evidence_file_id: uuid.UUID | None = Field(default=None, description="Associated re-check evidence photo file ID")
    notes: str | None = Field(default=None, description="Staff completion comments / corrective action summary")


class VerifyCAPARequest(BaseModel):
    approved: bool = Field(..., description="True to verify and close incident, False to reopen CAPA")
    notes: str | None = Field(default=None, description="Manager verification notes or reopening reason")


class DirectStatusPatchRequest(BaseModel):
    status: str | None = Field(default=None, description="Attempted status patch")
