import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID | None = None
    user_id: uuid.UUID
    outbox_event_id: uuid.UUID | None = None
    title: str
    message: str
    event_type: str
    read_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    event_type: str
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceUpdate(BaseModel):
    channel: str = "IN_APP"
    event_type: str
    enabled: bool
