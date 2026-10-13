import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class PresignRequest(BaseModel):
    filename: str = Field(..., description="Original filename of the file to be uploaded")
    mime_type: str = Field(
        ..., description="Declared MIME type (must be image/jpeg, image/png, or image/webp)"
    )
    size_bytes: int = Field(..., description="Declared size of the file in bytes (max 10MB)")
    purpose: str | None = Field(
        default="ENTRY_EVIDENCE", description="Optional purpose tag for upload"
    )
    restaurant_id: uuid.UUID | None = Field(
        default=None, description="Outlet restaurant ID (defaults to TenantContext)"
    )


class PresignResponse(BaseModel):
    id: uuid.UUID
    upload_url: str
    storage_key: str
    expires_in_seconds: int = 900


class EvidenceFileResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    uploaded_by: uuid.UUID
    storage_key: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    upload_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
