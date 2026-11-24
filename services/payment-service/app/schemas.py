import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CreatePaymentRequest(BaseModel):
    booking_code: str = Field(min_length=4, max_length=40)


class PaymentWebhookRequest(BaseModel):
    booking_code: str = Field(min_length=4, max_length=40)
    amount: float = Field(gt=0)
    provider_tx_id: str = Field(min_length=3, max_length=80)
    provider: str = Field(default="VIETQR_GATEWAY", max_length=30)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    booking_code: str
    amount: float
    transfer_content: str
    qr_image_url: str
    bank_bin: str
    bank_account_no: str
    bank_account_name: str
    provider: str
    provider_tx_id: str | None
    status: str
    expires_at: datetime
    paid_at: datetime | None
    created_at: datetime
