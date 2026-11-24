import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, JSON, Numeric, String, Text, Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    booking_code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transfer_content: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    qr_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    bank_bin: Mapped[str] = mapped_column(String(20), nullable=False)
    bank_account_no: Mapped[str] = mapped_column(String(40), nullable=False)
    bank_account_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="VIETQR")
    provider_tx_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", index=True
    )  # PENDING | SUCCEEDED | EXPIRED | CANCELLED
    booking_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
