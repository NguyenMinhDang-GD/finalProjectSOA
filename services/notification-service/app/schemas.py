import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_code: str
    recipient_email: str
    subject: str
    channel: str
    status: str
    retry_count: int
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime
