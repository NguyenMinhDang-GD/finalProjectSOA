import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    booking_code: str
    customer_name: str
    customer_email: str
    customer_phone: str
    court_name: str
    branch_name: str = ""
    location_name: str = ""
    location_address: str = ""
    play_date: date
    start_hour: int
    end_hour: int
    total_amount: float
    qr_payload: str
    status: str
    checked_in_by: str | None
    checked_in_at: datetime | None
    created_at: datetime
    qr_image_base64: str | None = None


class ScanQRRequest(BaseModel):
    qr_data: str = Field(min_length=4, max_length=500)
    bypass_time_check: bool = False


class ScanQRResponse(BaseModel):
    valid: bool
    code: str
    message: str
    ticket: TicketResponse | None = None
