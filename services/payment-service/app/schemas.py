import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_exact_vnd(value: int | float | Decimal) -> int:
    dec = Decimal(str(value))
    if dec != dec.to_integral_value():
        raise ValueError("Số tiền VND phải là số nguyên, không hỗ trợ phần thập phân")
    return int(dec)


class CreatePaymentRequest(BaseModel):
    booking_code: str = Field(min_length=4, max_length=40)


class PaymentWebhookRequest(BaseModel):
    booking_code: str = Field(min_length=4, max_length=40)
    amount: int | float = Field(gt=0)
    provider_tx_id: str = Field(min_length=3, max_length=80)
    provider: str = Field(default="SIMULATED_GATEWAY", max_length=30)
    outcome: Literal["SUCCEEDED", "FAILED", "PROCESSING"] = "SUCCEEDED"
    failure_reason: str | None = Field(default=None, max_length=240)

    @field_validator("amount")
    @classmethod
    def check_integer_vnd(cls, v: int | float) -> int:
        return validate_exact_vnd(v)


class SimulatePaymentRequest(BaseModel):
    outcome: Literal[
        "PROCESSING",
        "SUCCEEDED",
        "FAILED",
        "UNDERPAID",
        "OVERPAID",
        "DUPLICATE",
        "LATE",
    ] = "SUCCEEDED"
    amount: int | None = Field(default=None, gt=0)
    provider_tx_id: str | None = Field(default=None, min_length=3, max_length=80)
    failure_reason: str | None = Field(default=None, max_length=240)


class PaymentAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    booking_code: str
    attempt_number: int
    provider: str
    provider_tx_id: str | None
    outcome: str
    expected_amount: int
    received_amount: int
    failure_reason: str | None
    initiated_by: str
    created_at: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    booking_code: str
    amount: float
    expected_amount: int
    received_amount: int
    refunded_amount: int
    currency: str = "VND"
    payment_mode: str = "MOCK_DEMO"
    simulation_notice: str
    transfer_content: str
    qr_image_url: str
    bank_bin: str
    bank_account_no: str
    bank_account_name: str
    provider: str
    provider_tx_id: str | None
    status: str
    attempt_count: int = 0
    failure_reason: str | None = None
    last_attempt_at: datetime | None = None
    reconciliation_status: str = "NONE"
    reconciliation_note: str | None = None
    expires_at: datetime
    paid_at: datetime | None
    created_at: datetime


class ReconciliationCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID | None
    booking_code: str
    case_type: str
    status: str
    expected_amount: int
    received_amount: int
    discrepancy_amount: int
    provider_tx_id: str | None
    resolution_action: str | None
    resolution_note: str | None
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UpdateReconciliationRequest(BaseModel):
    status: Literal["IN_REVIEW", "RESOLVED"]
    resolution_action: str | None = Field(default=None, max_length=60)
    resolution_note: str = Field(min_length=3, max_length=500)


class CreateRefundRequest(BaseModel):
    booking_code: str = Field(min_length=4, max_length=40)
    requested_amount: int = Field(gt=0)
    policy_tier: Literal[
        "FULL_24H",
        "PARTIAL_2H_24H",
        "NON_REFUNDABLE_LT_2H",
        "ADMIN_EXCEPTION",
        "OVERPAYMENT_EXCESS",
    ] = "FULL_24H"
    policy_percent: int = Field(default=100, ge=0, le=100)
    reason: str = Field(min_length=3, max_length=500)
    admin_override_reason: str | None = Field(default=None, max_length=500)
    auto_approve: bool = False


class ApproveRefundRequest(BaseModel):
    approved_amount: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


class RejectRefundRequest(BaseModel):
    rejection_reason: str = Field(min_length=3, max_length=500)


class ExecuteRefundRequest(BaseModel):
    outcome: Literal["SUCCEEDED", "FAILED", "PROCESSING"] = "SUCCEEDED"
    failure_reason: str | None = Field(default=None, max_length=240)


class RefundCallbackRequest(BaseModel):
    refund_code: str = Field(min_length=4, max_length=50)
    provider_refund_id: str = Field(min_length=3, max_length=80)
    outcome: Literal["SUCCEEDED", "FAILED"]
    failure_reason: str | None = Field(default=None, max_length=240)


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    booking_id: uuid.UUID
    booking_code: str
    refund_code: str
    original_paid_amount: int
    requested_amount: int
    approved_amount: int
    refunded_amount: int
    policy_tier: str
    policy_percent: int
    status: str
    reason: str
    rejection_reason: str | None
    admin_override_reason: str | None
    failure_reason: str | None
    provider: str
    provider_refund_id: str | None
    retry_count: int
    requested_by: str
    approved_by: str | None
    processed_by: str | None
    created_at: datetime
    approved_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class FinancialAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: str
    booking_code: str
    action: str
    actor: str
    actor_role: str
    previous_state: str | None
    new_state: str | None
    amount_vnd: int
    reason: str | None
    metadata_json: dict
    created_at: datetime
