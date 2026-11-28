import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    title_note: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    locations: Mapped[list["Location"]] = relationship(
        back_populates="branch", lazy="selectin"
    )


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    branch: Mapped["Branch"] = relationship(back_populates="locations", lazy="selectin")
    courts: Mapped[list["Court"]] = relationship(back_populates="location", lazy="selectin")


class Court(Base):
    __tablename__ = "courts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    court_type: Mapped[str] = mapped_column(String(20), nullable=False)  # INDOOR | OUTDOOR
    surface: Mapped[str] = mapped_column(String(80), nullable=False, default="Acrylic 7 lớp chuẩn thi đấu")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")  # ACTIVE | MAINTENANCE
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    location: Mapped["Location | None"] = relationship(back_populates="courts", lazy="selectin")


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    court_type: Mapped[str] = mapped_column(String(20), nullable=False)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_peak_hour: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_per_hour: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class BookingOrder(Base):
    __tablename__ = "booking_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    court_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courts.id"), nullable=False)
    court_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    branch_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    location_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    location_address_snapshot: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    play_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING_PAYMENT", index=True
    )  # PENDING_PAYMENT | PAID | CANCELLED | EXPIRED
    guest_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    guest_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    guest_token_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    booking_source: Mapped[str] = mapped_column(String(20), nullable=False, default="ONLINE")  # ONLINE | WALK_IN
    booking_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    admission_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE")
    admission_ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    no_show_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    no_show_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    slots: Mapped[list["BookingSlot"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", lazy="selectin"
    )


class BookingSlot(Base):
    __tablename__ = "booking_slots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking_orders.id", ondelete="CASCADE"), nullable=False
    )
    court_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courts.id"), nullable=False)
    play_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_peak_hour: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    slot_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="LOCKED"
    )  # LOCKED | BOOKED | RELEASED

    booking: Mapped["BookingOrder"] = relationship(back_populates="slots")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_booking_outbox_pending", "status", "next_retry_at", "created_at"),
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
        UniqueConstraint("consumer_name", "event_id", name="uq_booking_inbox_consumer_event"),
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


class BookingRescheduleHistory(Base):
    __tablename__ = "booking_reschedule_history"
    __table_args__ = (
        Index("ix_reschedule_booking_created", "booking_code", "created_at"),
        UniqueConstraint("booking_code", "idempotency_key", name="uq_reschedule_booking_idem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    booking_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    previous_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    new_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_court_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    previous_court_name: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_play_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    new_court_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    new_court_name: Mapped[str] = mapped_column(String(120), nullable=False)
    new_play_date: Mapped[date] = mapped_column(Date, nullable=False)
    new_start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    new_end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    new_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class MaintenanceBlock(Base):
    __tablename__ = "maintenance_blocks"
    __table_args__ = (
        Index("ix_maintenance_court_date_status", "court_id", "play_date", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    court_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courts.id"), nullable=False, index=True)
    court_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    play_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SCHEDULED", index=True
    )  # SCHEDULED | CANCELLED | COMPLETED
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    cancelled_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class OperationalAuditLog(Base):
    __tablename__ = "operational_audit_logs"
    __table_args__ = (
        Index("ix_op_audit_entity_created", "entity_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False)
    previous_state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class BookingCompensation(Base):
    __tablename__ = "booking_compensations"
    __table_args__ = (
        UniqueConstraint("booking_code", "payment_id", name="uq_booking_comp_code_payment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    booking_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payment_id: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_tx_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="COMPENSATION_REQUIRED", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
