import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import quote

import aio_pika
import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.events.rabbitmq import rmq_client
from app.metrics import PAYMENTS_CONFIRMED_TOTAL
from app.models import PaymentTransaction
from app.schemas import PaymentResponse

logger = logging.getLogger(__name__)


def build_vietqr_url(amount: float, transfer_content: str) -> str:
    return (
        f"https://img.vietqr.io/image/{settings.vietqr_bank_bin}-{settings.vietqr_account_no}-compact2.png"
        f"?amount={int(round(amount))}&addInfo={quote(transfer_content)}&accountName={quote(settings.vietqr_account_name)}"
    )


def verify_webhook_signature(booking_code: str, amount: float, provider_tx_id: str, signature: str | None) -> bool:
    if not signature:
        return False
    canonical = f"{booking_code}:{int(round(amount))}:{provider_tx_id}"
    expected = hmac.new(
        settings.webhook_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


async def fetch_booking_from_service(booking_code: str) -> dict:
    url = f"{settings.booking_service_url}/api/bookings/internal/{booking_code.strip()}"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url, headers={"X-Internal-Key": settings.internal_api_key})
    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    if resp.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Lỗi kết nối Court Booking Service")
    return resp.json()


async def create_or_get_payment(db: AsyncSession, booking_code: str) -> PaymentResponse:
    existing = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.booking_code == booking_code.strip())
    )
    if existing:
        return PaymentResponse.model_validate(existing)

    booking = await fetch_booking_from_service(booking_code)
    if booking["status"] != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đơn đặt sân đang ở trạng thái {booking['status']}, không thể tạo thanh toán mới",
        )

    amount = float(booking["total_amount"])
    transfer_content = f"PKB {booking['booking_code']}"
    qr_url = build_vietqr_url(amount, transfer_content)

    tx = PaymentTransaction(
        booking_id=uuid.UUID(booking["id"]),
        booking_code=booking["booking_code"],
        amount=Decimal(str(booking["total_amount"])),
        transfer_content=transfer_content,
        qr_image_url=qr_url,
        bank_bin=settings.vietqr_bank_bin,
        bank_account_no=settings.vietqr_account_no,
        bank_account_name=settings.vietqr_account_name,
        provider="VIETQR",
        status="PENDING",
        booking_snapshot={
            "booking_id": booking["id"],
            "booking_code": booking["booking_code"],
            "customer_name": booking["customer_name"],
            "customer_phone": booking["customer_phone"],
            "customer_email": booking["customer_email"],
            "court_name": booking["court_name_snapshot"],
            "branch_name": booking.get("branch_name_snapshot", ""),
            "location_name": booking.get("location_name_snapshot", ""),
            "location_address": booking.get("location_address_snapshot", ""),
            "play_date": booking["play_date"],
            "start_hour": booking["start_hour"],
            "end_hour": booking["end_hour"],
            "total_amount": booking["total_amount"],
        },
        expires_at=datetime.fromisoformat(booking["expires_at"]),
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return PaymentResponse.model_validate(tx)


async def confirm_payment_idempotent(
    db: AsyncSession,
    booking_code: str,
    provider_tx_id: str,
    provider: str = "VIETQR_GATEWAY",
    amount_paid: float | None = None,
) -> PaymentResponse:
    tx = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.booking_code == booking_code.strip())
    )
    if not tx:
        # Auto-create transaction record if webhook arrives before explicit /create call
        await create_or_get_payment(db, booking_code)
        tx = await db.scalar(
            select(PaymentTransaction).where(PaymentTransaction.booking_code == booking_code.strip())
        )
        assert tx is not None

    # Idempotency check
    if tx.status == "SUCCEEDED":
        return PaymentResponse.model_validate(tx)

    if tx.status in ("EXPIRED", "CANCELLED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Giao dịch đã ở trạng thái {tx.status}, không thể xác nhận thanh toán",
        )

    if amount_paid is not None and int(round(amount_paid)) < int(round(float(tx.amount))):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số tiền thanh toán không đủ")

    now_utc = datetime.now(timezone.utc)
    tx.status = "SUCCEEDED"
    tx.provider = provider
    tx.provider_tx_id = provider_tx_id
    tx.paid_at = now_utc
    await db.commit()
    await db.refresh(tx)

    PAYMENTS_CONFIRMED_TOTAL.labels(provider=provider).inc()

    snapshot = tx.booking_snapshot or {}
    await rmq_client.publish(
        "payment.succeeded",
        {
            "event": "payment.succeeded",
            "payment_id": str(tx.id),
            "provider": provider,
            "provider_tx_id": provider_tx_id,
            "paid_at": now_utc.isoformat(),
            **snapshot,
        },
    )
    return PaymentResponse.model_validate(tx)


async def start_booking_lifecycle_consumer() -> None:
    if not rmq_client.channel or not rmq_client.exchange:
        return
    queue = await rmq_client.channel.declare_queue("payment.booking_events", durable=True)
    await queue.bind(rmq_client.exchange, routing_key="booking.expired")
    await queue.bind(rmq_client.exchange, routing_key="booking.cancelled")

    async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            data = json.loads(message.body.decode("utf-8"))
            booking_code = data.get("booking_code")
            event_name = data.get("event")
            if not booking_code:
                return
            async with AsyncSessionLocal() as db:
                tx = await db.scalar(
                    select(PaymentTransaction).where(PaymentTransaction.booking_code == booking_code)
                )
                if tx and tx.status == "PENDING":
                    tx.status = "EXPIRED" if event_name == "booking.expired" else "CANCELLED"
                    await db.commit()
                    logger.info("Updated payment %s to %s", booking_code, tx.status)

    await queue.consume(_on_message)
