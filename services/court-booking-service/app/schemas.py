import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


CourtType = Literal["INDOOR", "OUTDOOR"]
CourtStatus = Literal["ACTIVE", "MAINTENANCE"]


class BranchCreateRequest(BaseModel):
    title_note: str = Field(default="", max_length=150)


class BranchUpdateRequest(BaseModel):
    title_note: str = Field(default="", max_length=150)


class LocationCreateRequest(BaseModel):
    branch_id: uuid.UUID
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=3, max_length=300)


class LocationUpdateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, min_length=3, max_length=300)


class LocationResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_number: int
    branch_name: str
    name: str
    address: str
    court_count: int = 0
    created_at: datetime


class BranchResponse(BaseModel):
    id: uuid.UUID
    branch_number: int
    title_note: str
    display_name: str
    locations: list[LocationResponse] = []
    created_at: datetime


class CourtCreateRequest(BaseModel):
    location_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    court_type: CourtType
    surface: str = Field(default="Acrylic 7 lớp chuẩn thi đấu", max_length=80)
    description: str = Field(default="", max_length=500)


class CourtUpdateRequest(BaseModel):
    location_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=120)
    court_type: CourtType | None = None
    surface: str | None = Field(default=None, max_length=80)
    status: CourtStatus | None = None
    description: str | None = Field(default=None, max_length=500)


class CourtResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    branch_number: int | None = None
    branch_name: str = ""
    location_name: str = ""
    location_address: str = ""
    name: str
    court_type: str
    surface: str
    status: str
    description: str
    created_at: datetime


class DeleteActionResponse(BaseModel):
    deleted: bool
    mode: Literal["hard", "soft"]
    message: str


class PricingRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    court_type: str
    start_hour: int
    end_hour: int
    is_weekend: bool
    is_peak_hour: bool
    price_per_hour: float


class PricingRuleUpdateRequest(BaseModel):
    price_per_hour: Decimal = Field(gt=0, le=5000000)


class AvailabilitySlotItem(BaseModel):
    start_hour: int
    end_hour: int
    label: str
    price: float
    is_peak_hour: bool
    status: Literal["AVAILABLE", "LOCKED", "BOOKED", "MAINTENANCE", "PAST"]


class CourtAvailabilityItem(BaseModel):
    court: CourtResponse
    slots: list[AvailabilitySlotItem]


class AvailabilityResponse(BaseModel):
    play_date: date
    is_weekend: bool
    courts: list[CourtAvailabilityItem]


class CreateBookingRequest(BaseModel):
    court_id: uuid.UUID
    play_date: date
    hours: list[int] = Field(min_length=1, max_length=6)
    customer_name: str = Field(min_length=2, max_length=150)
    customer_phone: str = Field(min_length=8, max_length=20)
    customer_email: EmailStr

    @field_validator("hours")
    @classmethod
    def validate_contiguous_hours(cls, v: list[int]) -> list[int]:
        unique_sorted = sorted(set(v))
        if len(unique_sorted) != len(v):
            raise ValueError("Danh sách khung giờ không được trùng lặp")
        for h in unique_sorted:
            if h < 5 or h > 21:
                raise ValueError("Khung giờ đặt sân hợp lệ từ 05:00 đến 22:00 (start_hour 5..21)")
        for i in range(len(unique_sorted) - 1):
            if unique_sorted[i + 1] != unique_sorted[i] + 1:
                raise ValueError("Các slot trong cùng một đơn đặt phải liên tiếp nhau")
        return unique_sorted


class BookingSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start_hour: int
    end_hour: int
    slot_price: float
    is_peak_hour: bool
    slot_status: str


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_code: str
    user_id: uuid.UUID | None
    customer_name: str
    customer_phone: str
    customer_email: str
    court_id: uuid.UUID
    court_name_snapshot: str
    branch_name_snapshot: str = ""
    location_name_snapshot: str = ""
    location_address_snapshot: str = ""
    play_date: date
    start_hour: int
    end_hour: int
    total_amount: float
    status: str
    cancel_reason: str | None
    expires_at: datetime
    paid_at: datetime | None
    created_at: datetime
    slots: list[BookingSlotResponse]
    guest_access_token: str | None = None


class BookingAuthorizeRequest(BaseModel):
    user_id: str | None = None
    role: str | None = None
    guest_token: str | None = None
    require_owner: bool = False


class BookingAuthorizeResponse(BaseModel):
    authorized: bool
    booking_code: str
    status: str
    total_amount: float
    reason: str | None = None


class ClaimCheckinRequest(BaseModel):
    ticket_id: str = Field(min_length=4, max_length=64)
    staff_email: str = Field(min_length=2, max_length=150)


class ClaimCheckinResponse(BaseModel):
    admitted: bool
    already_admitted_same_ticket: bool = False
    booking_code: str
    status: str
    admission_status: str
    message: str


class CancelBookingRequest(BaseModel):
    reason: str = Field(default="Khách hàng hủy đặt sân", max_length=300)
    admin_exception: bool = False
    override_refund_percent: int | None = Field(default=None, ge=0, le=100)


class CancellationQuoteResponse(BaseModel):
    booking_code: str
    status: str
    eligible: bool
    is_checked_in: bool = False
    hours_until_play: float
    policy_tier: str
    refund_percent: int
    total_amount: int
    estimated_refund_amount: int
    message: str


class AdminStatsResponse(BaseModel):
    total_bookings: int
    paid_bookings: int
    pending_bookings: int
    cancelled_or_expired: int
    total_revenue: float
    active_courts: int
