import asyncio
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.events.outbox import claim_inbox_event, enqueue_outbox_event, resolve_event_id
from app.events.rabbitmq import DLX_NAME, rmq_client
from app.metrics import (
    EVENTS_DLQ_TOTAL,
    EVENTS_DUPLICATE_TOTAL,
    EVENTS_RETRY_TOTAL,
    PAYMENTS_CONFIRMED_TOTAL,
    PAYMENT_COMPENSATION_REQUIRED_TOTAL,
)
from app.models import PaymentCompensation, PaymentTransaction
from app.schemas import PaymentResponse

logger = logging.getLogger(__name__)


def build_vietqr_url(amount: float, transfer_content: str) -> str:
    return (
        f"https://img.vietqr.io/image/{settings.vietqr_bank_bin}-{settings.vietqr_account_no}-compact2.png"
        f"?amount={int(round(amount))}&addInfo={quote(transfer_content)}&accountName={quote(settings.vietqr_account_name)}"
    )


def verify_webhook_signature(booking_code: str, amount: float, provider_tx_id: str, signature: str | None) -> bool:
    if not settings.webhook_secret or not signature:
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
    code = booking_code.strip()
    existing = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.booking_code == code)
    )
    if existing:
        return PaymentResponse.model_validate(existing)

    booking = await fetch_booking_from_service(code)
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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(PaymentTransaction).where(PaymentTransaction.booking_code == code)
        )
        if existing:
            return PaymentResponse.model_validate(existing)
        raise
    await db.refresh(tx)
    return PaymentResponse.model_validate(tx)


async def confirm_payment_idempotent(
    db: AsyncSession,
    booking_code: str,
    provider_tx_id: str,
    provider: str = "VIETQR_GATEWAY",
    amount_paid: float | None = None,
) -> PaymentResponse:
    code = booking_code.strip()
    tx = await db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.booking_code == code)
        .with_for_update()
    )
    if not tx:
        # Auto-create transaction record if webhook arrives before explicit /create call
        try:
            await create_or_get_payment(db, code)
        except HTTPException as exc:
            # Preserve webhook funds evidence even if booking is already EXPIRED/CANCELLED
            if amount_paid is not None and exc.status_code == status.HTTP_400_BAD_REQUEST:
                booking = await fetch_booking_from_service(code)
                tx = PaymentTransaction(
                    booking_id=uuid.UUID(booking["id"]),
                    booking_code=booking["booking_code"],
                    amount=Decimal(str(booking["total_amount"])),
                    transfer_content=f"PKB {booking['booking_code']}",
                    qr_image_url=build_vietqr_url(float(booking["total_amount"]), f"PKB {booking['booking_code']}"),
                    bank_bin=settings.vietqr_bank_bin,
                    bank_account_no=settings.vietqr_account_no,
                    bank_account_name=settings.vietqr_account_name,
                    provider=provider,
                    provider_tx_id=provider_tx_id,
                    status=booking["status"] if booking["status"] in ("EXPIRED", "CANCELLED") else "EXPIRED",
                    reconciliation_status="COMPENSATION_REQUIRED",
                    reconciliation_note=f"Late webhook payment received for booking status {booking['status']}",
                    booking_snapshot={"booking_id": booking["id"], "booking_code": booking["booking_code"]},
                    expires_at=datetime.fromisoformat(booking["expires_at"]),
                    paid_at=datetime.now(timezone.utc),
                )
                db.add(tx)
                db.add(
                    PaymentCompensation(
                        payment_id=tx.id,
                        booking_code=code,
                        provider=provider,
                        provider_tx_id=provider_tx_id,
                        amount=Decimal(str(amount_paid)),
                        reason=f"LATE_PAYMENT_BOOKING_{booking['status']}",
                        status="COMPENSATION_REQUIRED",
                    )
                )
                enqueue_outbox_event(
                    db,
                    event_type="payment.compensation_required",
                    aggregate_id=code,
                    payload={
                        "payment_id": str(tx.id),
                        "booking_code": code,
                        "provider": provider,
                        "provider_tx_id": provider_tx_id,
                        "amount": float(amount_paid),
                        "reason": f"LATE_PAYMENT_BOOKING_{booking['status']}",
                    },
                )
                await db.commit()
                await db.refresh(tx)
                PAYMENT_COMPENSATION_REQUIRED_TOTAL.labels(reason="late_payment").inc()
                return PaymentResponse.model_validate(tx)
            raise
        tx = await db.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.booking_code == code)
            .with_for_update()
        )
        assert tx is not None

    # Idempotency check
    if tx.status == "SUCCEEDED":
        return PaymentResponse.model_validate(tx)

    if tx.status in ("EXPIRED", "CANCELLED"):
        if amount_paid is not None:
            existing_comp = await db.scalar(
                select(PaymentCompensation).where(
                    PaymentCompensation.booking_code == code,
                    PaymentCompensation.provider_tx_id == provider_tx_id,
                )
            )
            if not existing_comp:
                tx.reconciliation_status = "COMPENSATION_REQUIRED"
                tx.reconciliation_note = f"Late webhook payment received while payment status is {tx.status}"
                if not tx.provider_tx_id:
                    tx.provider_tx_id = provider_tx_id
                    tx.provider = provider
                    tx.paid_at = datetime.now(timezone.utc)
                db.add(
                    PaymentCompensation(
                        payment_id=tx.id,
                        booking_code=code,
                        provider=provider,
                        provider_tx_id=provider_tx_id,
                        amount=Decimal(str(amount_paid)),
                        reason=f"LATE_PAYMENT_TX_{tx.status}",
                        status="COMPENSATION_REQUIRED",
                    )
                )
                enqueue_outbox_event(
                    db,
                    event_type="payment.compensation_required",
                    aggregate_id=code,
                    payload={
                        "payment_id": str(tx.id),
                        "booking_code": code,
                        "provider": provider,
                        "provider_tx_id": provider_tx_id,
                        "amount": float(amount_paid),
                        "reason": f"LATE_PAYMENT_TX_{tx.status}",
                    },
                )
                await db.commit()
                await db.refresh(tx)
                PAYMENT_COMPENSATION_REQUIRED_TOTAL.labels(reason="late_payment").inc()
            return PaymentResponse.model_validate(tx)
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

    snapshot = tx.booking_snapshot or {}
    enqueue_outbox_event(
        db,
        event_type="payment.succeeded",
        aggregate_id=tx.booking_code,
        payload={
            "payment_id": str(tx.id),
            "provider": provider,
            "provider_tx_id": provider_tx_id,
            "paid_at": now_utc.isoformat(),
            **snapshot,
        },
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mã giao dịch provider_tx_id đã được sử dụng cho đơn khác",
        )
    await db.refresh(tx)

    PAYMENTS_CONFIRMED_TOTAL.labels(provider=provider).inc()
    return PaymentResponse.model_validate(tx)


async def _handle_booking_lifecycle_event(data: dict) -> None:
    booking_code = str(data["booking_code"]).strip()
    event_name = str(data["event"])
    event_id = resolve_event_id(data, f"{event_name}:{booking_code}:{data.get('payment_id', '')}")
    correlation_id = str(data.get("correlation_id") or event_id)

    async with AsyncSessionLocal() as db:
        claimed = await claim_inbox_event(
            db,
            consumer_name="payment-service.booking_events",
            event_id=event_id,
            event_type=event_name,
            correlation_id=correlation_id,
        )
        if not claimed:
            EVENTS_DUPLICATE_TOTAL.labels(
                service=settings.service_name, event_type=event_name
            ).inc()
            return

        tx = await db.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.booking_code == booking_code)
            .with_for_update()
        )
        if event_name in ("booking.expired", "booking.cancelled"):
            if tx and tx.status == "PENDING":
                tx.status = "EXPIRED" if event_name == "booking.expired" else "CANCELLED"
                logger.info("Updated payment %s to %s", booking_code, tx.status)
        elif event_name == "booking.confirmation_failed":
            reason = str(data.get("reason") or "BOOKING_CONFIRMATION_FAILED")
            if tx:
                tx.reconciliation_status = "COMPENSATION_REQUIRED"
                tx.reconciliation_note = reason
            provider_tx_id = data.get("provider_tx_id") or (tx.provider_tx_id if tx else None)
            existing_comp = await db.scalar(
                select(PaymentCompensation).where(
                    PaymentCompensation.booking_code == booking_code,
                    PaymentCompensation.provider_tx_id == provider_tx_id,
                )
            )
            if not existing_comp:
                db.add(
                    PaymentCompensation(
                        payment_id=tx.id if tx else None,
                        booking_code=booking_code,
                        provider=tx.provider if tx else "VIETQR_GATEWAY",
                        provider_tx_id=provider_tx_id,
                        amount=tx.amount if tx else Decimal(str(data.get("total_amount", 0))),
                        reason=reason,
                        status="COMPENSATION_REQUIRED",
                    )
                )
            PAYMENT_COMPENSATION_REQUIRED_TOTAL.labels(reason="booking_confirmation_failed").inc()
            logger.warning(
                "Payment flagged COMPENSATION_REQUIRED booking_code=%s reason=%s",
                booking_code,
                reason,
            )

        await db.commit()


async def start_booking_lifecycle_consumer() -> None:
    rmq_client.set_consumer_setup(_setup_booking_lifecycle_consumer)
    await _setup_booking_lifecycle_consumer()


async def _setup_booking_lifecycle_consumer() -> None:
    if not rmq_client.channel or not rmq_client.exchange:
        return
    queue = await rmq_client.channel.declare_queue(
        "payment.booking_events.v2",
        durable=True,
        arguments={"x-dead-letter-exchange": DLX_NAME},
    )
    await queue.bind(rmq_client.exchange, routing_key="booking.expired")
    await queue.bind(rmq_client.exchange, routing_key="booking.cancelled")
    await queue.bind(rmq_client.exchange, routing_key="booking.confirmation_failed")

    async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            data = json.loads(message.body.decode("utf-8"))
            if not isinstance(data, dict) or not data.get("booking_code") or not data.get("event"):
                raise ValueError("Missing booking_code or event in booking lifecycle message")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            logger.error("Permanent failure parsing payment.booking_events, routing to DLQ: %s", exc)
            EVENTS_DLQ_TOTAL.labels(
                service=settings.service_name, event_type="unknown"
            ).inc()
            await message.reject(requeue=False)
            return

        event_name = str(data.get("event", "unknown"))
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                await _handle_booking_lifecycle_event(data)
                await message.ack()
                return
            except Exception as exc:
                EVENTS_RETRY_TOTAL.labels(
                    service=settings.service_name, event_type=event_name
                ).inc()
                logger.warning(
                    "Transient error processing %s (attempt %s/%s): %s",
                    event_name,
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                else:
                    EVENTS_DLQ_TOTAL.labels(
                        service=settings.service_name, event_type=event_name
                    ).inc()
                    await message.reject(requeue=False)

    await queue.consume(_on_message)
