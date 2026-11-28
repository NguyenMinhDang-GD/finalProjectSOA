import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid as UUID,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.providers.simulated import SIMULATION_NOTICE_VI


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    booking_code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expected_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refunded_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="VND")
    payment_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="MOCK_DEMO")
    simulation_notice: Mapped[str] = mapped_column(Text, nullable=False, default=SIMULATION_NOTICE_VI)
    transfer_content: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    qr_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    bank_bin: Mapped[str] = mapped_column(String(20), nullable=False, default="SIMULATED")
    bank_account_no: Mapped[str] = mapped_column(String(40), nullable=False, default="DEMO-ONLY")
    bank_account_name: Mapped[str] = mapped_column(String(120), nullable=False, default="THANH TOÁN GIẢ LẬP")
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="SIMULATED_GATEWAY")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False, default="SIMULATED_ONLINE")
    booking_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    collected_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_tx_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", index=True
    )  # PENDING | PROCESSING | SUCCEEDED | FAILED | EXPIRED | CANCELLED
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciliation_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="NONE", index=True
    )  # NONE | OPEN | IN_REVIEW | RESOLVED | COMPENSATION_REQUIRED
    reconciliation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        Index("ix_payment_attempts_booking_created", "booking_code", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    booking_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="SIMULATED_GATEWAY")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False, default="SIMULATED_ONLINE")
    provider_tx_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    outcome: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # PROCESSING | SUCCEEDED | FAILED | UNDERPAID | OVERPAID | DUPLICATE | LATE | CANCELLED
    expected_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    initiated_by: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class ReconciliationCase(Base):
    __tablename__ = "reconciliation_cases"
    __table_args__ = (
        Index("ix_reconciliation_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    booking_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    case_type: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True
    )  # UNDERPAYMENT | OVERPAYMENT | DUPLICATE_PAYMENT | LATE_PAYMENT | CONFIRMATION_FAILED | REFUND_MISMATCH
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", index=True
    )  # OPEN | IN_REVIEW | RESOLVED
    expected_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discrepancy_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_tx_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolution_action: Mapped[str | None] = mapped_column(String(60), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class RefundTransaction(Base):
    __tablename__ = "refund_transactions"
    __table_args__ = (
        Index("ix_refunds_booking_status", "booking_code", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    booking_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    refund_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    original_paid_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requested_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refunded_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    policy_tier: Mapped[str] = mapped_column(
        String(40), nullable=False, default="FULL_24H"
    )  # FULL_24H | PARTIAL_2H_24H | NON_REFUNDABLE_LT_2H | ADMIN_EXCEPTION | OVERPAYMENT_EXCESS
    policy_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="REQUESTED", index=True
    )  # REQUESTED | APPROVED | PROCESSING | SUCCEEDED | FAILED | REJECTED
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="SIMULATED_GATEWAY")
    provider_refund_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False, default="customer")
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class FinancialAuditLog(Base):
    __tablename__ = "financial_audit_logs"
    __table_args__ = (
        Index("ix_fin_audit_booking_created", "booking_code", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # PAYMENT | REFUND | RECONCILIATION | CANCELLATION
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    booking_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False, default="SYSTEM")
    previous_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_payment_outbox_pending", "status", "next_retry_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    correlation_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    causation_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", index=True
    )  # PENDING | PUBLISHED | FAILED
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class InboxEvent(Base):
    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("consumer_name", "event_id", name="uq_payment_inbox_consumer_event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consumer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROCESSED")
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class PaymentCompensation(Base):
    __tablename__ = "payment_compensations"
    __table_args__ = (
        UniqueConstraint("booking_code", "provider_tx_id", name="uq_payment_comp_code_tx"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    booking_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="SIMULATED_GATEWAY")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False, default="SIMULATED_ONLINE")
    booking_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    collected_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_tx_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="COMPENSATION_REQUIRED", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
