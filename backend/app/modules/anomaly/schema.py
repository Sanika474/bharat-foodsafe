import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class AnomalyResultResponse(BaseModel):
    id: uuid.UUID
    entry_id: uuid.UUID
    model_version_id: uuid.UUID | None = None
    baseline_score: float | None = None
    ml_score: float | None = None
    decision: str
    reasons_jsonb: Any | None = None
    analyzed_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnomalyQueueItemResponse(BaseModel):
    id: uuid.UUID
    entry_id: uuid.UUID
    restaurant_id: uuid.UUID
    task_name: str | None = None
    user_name: str | None = None
    decision: str
    ml_score: float | None = None
    baseline_score: float | None = None
    reasons_jsonb: Any | None = None
    analyzed_at: datetime

    class Config:
        from_attributes = True
