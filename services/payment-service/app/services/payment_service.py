import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import aio_pika
import httpx
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
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
    CASH_COLLECTIONS_TOTAL,
    PAYMENTS_CONFIRMED_TOTAL,
    PAYMENTS_FAILED_TOTAL,
    PAYMENT_COMPENSATION_REQUIRED_TOTAL,
    PAYMENT_RECONCILIATION_CASES_TOTAL,
    REFUNDS_TOTAL,
)
from app.models import (
    FinancialAuditLog,
    PaymentAttempt,
    PaymentCompensation,
    PaymentTransaction,
    ReconciliationCase,
    RefundTransaction,
)
from app.providers import SIMULATION_NOTICE_VI, build_non_financial_demo_qr, get_payment_provider
from app.schemas import (
    FinancialAuditLogResponse,
    PaymentAttemptResponse,
    PaymentResponse,
    ReconciliationCaseResponse,
    RefundResponse,
)

logger = logging.getLogger(__name__)


def verify_webhook_signature(
    booking_code: str,
    amount: int | float,
    provider_tx_id: str,
    signature: str | None,
) -> bool:
    if not settings.webhook_secret or not signature:
        return False
    canonical = f"{booking_code}:{int(round(float(amount)))}:{provider_tx_id}"
    expected = hmac.new(
        settings.webhook_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def verify_refund_callback_signature(
    refund_code: str,
    provider_refund_id: str,
    outcome: str,
    signature: str | None,
) -> bool:
    if not settings.webhook_secret or not signature:
        return False
    canonical = f"{refund_code}:{provider_refund_id}:{outcome}"
    expected = hmac.new(
        settings.webhook_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def _record_audit(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    booking_code: str,
    action: str,
    actor: str,
    actor_role: str,
    previous_state: str | None,
    new_state: str | None,
    amount_vnd: int = 0,
    reason: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        FinancialAuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            booking_code=booking_code,
            action=action,
            actor=actor,
            actor_role=actor_role,
            previous_state=previous_state,
            new_state=new_state,
            amount_vnd=amount_vnd,
            reason=reason,
            metadata_json=metadata or {},
        )
    )


async def fetch_booking_from_service(booking_code: str) -> dict:
    url = f"{settings.booking_service_url}/api/bookings/internal/{booking_code.strip()}"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url, headers={"X-Internal-Key": settings.internal_api_key})
    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    if resp.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Lỗi kết nối Court Booking Service")
    return resp.json()


def _require_provider():
    provider = get_payment_provider(settings.normalized_payment_mode)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cổng thanh toán giả lập đang ở chế độ DISABLED",
        )
    return provider


async def create_or_get_payment(db: AsyncSession, booking_code: str) -> PaymentResponse:
    code = booking_code.strip()
    existing = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.booking_code == code)
    )
    if existing:
        return PaymentResponse.model_validate(existing)

    provider = _require_provider()
    booking = await fetch_booking_from_service(code)
    if booking["status"] != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đơn đặt sân đang ở trạng thái {booking['status']}, không thể tạo thanh toán mới",
        )

    expected_vnd = int(round(float(booking["total_amount"])))
    transfer_content = f"PKB {booking['booking_code']}"
    session = provider.create_checkout_session(
        booking_code=booking["booking_code"],
        amount_vnd=expected_vnd,
        payment_mode=settings.normalized_payment_mode,
    )

    tx = PaymentTransaction(
        booking_id=uuid.UUID(booking["id"]),
        booking_code=booking["booking_code"],
        amount=Decimal(str(expected_vnd)),
        expected_amount=expected_vnd,
        received_amount=0,
        refunded_amount=0,
        currency="VND",
        payment_mode=session.payment_mode,
        simulation_notice=session.simulation_notice,
        transfer_content=transfer_content,
        qr_image_url=session.qr_image_url,
        bank_bin=session.bank_bin,
        bank_account_no=session.bank_account_no,
        bank_account_name=session.bank_account_name,
        provider=session.provider,
        payment_method="SIMULATED_ONLINE",
        booking_revision=int(booking.get("booking_revision") or 1),
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
            "total_amount": expected_vnd,
        },
        expires_at=datetime.fromisoformat(booking["expires_at"]),
    )
    db.add(tx)
    _record_audit(
        db,
        entity_type="PAYMENT",
        entity_id=str(tx.id),
        booking_code=tx.booking_code,
        action="PAYMENT_SESSION_CREATED",
        actor="system",
        actor_role="SYSTEM",
        previous_state=None,
        new_state="PENDING",
        amount_vnd=expected_vnd,
        reason="Khởi tạo phiên thanh toán giả lập (không phải giao dịch tiền thật)",
        metadata={"payment_mode": session.payment_mode, "provider": session.provider},
    )
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


async def _create_reconciliation_case(
    db: AsyncSession,
    *,
    payment: PaymentTransaction | None,
    booking_code: str,
    case_type: str,
    expected_amount: int,
    received_amount: int,
    provider_tx_id: str | None,
    note: str,
    actor: str = "system",
) -> ReconciliationCase:
    existing = None
    if provider_tx_id:
        existing = await db.scalar(
            select(ReconciliationCase).where(
                ReconciliationCase.booking_code == booking_code,
                ReconciliationCase.case_type == case_type,
                ReconciliationCase.provider_tx_id == provider_tx_id,
            )
        )
    if existing:
        return existing

    discrepancy = received_amount - expected_amount
    case = ReconciliationCase(
        payment_id=payment.id if payment else None,
        booking_code=booking_code,
        case_type=case_type,
        status="OPEN",
        expected_amount=expected_amount,
        received_amount=received_amount,
        discrepancy_amount=discrepancy,
        provider_tx_id=provider_tx_id,
        resolution_note=note,
    )
    db.add(case)
    await db.flush()
    PAYMENT_RECONCILIATION_CASES_TOTAL.labels(case_type=case_type).inc()
    _record_audit(
        db,
        entity_type="RECONCILIATION",
        entity_id=str(case.id),
        booking_code=booking_code,
        action="RECONCILIATION_CASE_OPENED",
        actor=actor,
        actor_role="SYSTEM",
        previous_state=None,
        new_state="OPEN",
        amount_vnd=abs(discrepancy),
        reason=note,
        metadata={"case_type": case_type, "provider_tx_id": provider_tx_id},
    )
    enqueue_outbox_event(
        db,
        event_type="payment.reconciliation_required",
        aggregate_id=booking_code,
        payload={
            "case_id": str(case.id),
            "booking_code": booking_code,
            "case_type": case_type,
            "expected_amount": expected_amount,
            "received_amount": received_amount,
            "discrepancy_amount": discrepancy,
            "provider_tx_id": provider_tx_id,
            "note": note,
        },
    )
    return case


async def _record_attempt(
    db: AsyncSession,
    *,
    tx: PaymentTransaction,
    provider: str,
    payment_method: str = "SIMULATED_ONLINE",
    provider_tx_id: str | None,
    outcome: str,
    received_amount: int,
    failure_reason: str | None = None,
    initiated_by: str = "system",
    raw_payload: dict | None = None,
) -> PaymentAttempt:
    tx.attempt_count = (tx.attempt_count or 0) + 1
    tx.last_attempt_at = datetime.now(timezone.utc)
    attempt = PaymentAttempt(
        payment_id=tx.id,
        booking_code=tx.booking_code,
        attempt_number=tx.attempt_count,
        provider=provider,
        payment_method=payment_method,
        provider_tx_id=provider_tx_id,
        outcome=outcome,
        expected_amount=tx.expected_amount or int(round(float(tx.amount))),
        received_amount=received_amount,
        failure_reason=failure_reason,
        initiated_by=initiated_by,
        raw_payload=raw_payload or {},
    )
    db.add(attempt)
    return attempt


async def _handle_late_payment(
    db: AsyncSession,
    *,
    tx: PaymentTransaction | None,
    booking: dict | None,
    booking_code: str,
    provider: str,
    provider_tx_id: str,
    received_vnd: int,
    initiated_by: str,
) -> PaymentResponse:
    now_utc = datetime.now(timezone.utc)
    if tx is None:
        assert booking is not None
        expected_vnd = int(round(float(booking["total_amount"])))
        tx_status = booking["status"] if booking["status"] in ("EXPIRED", "CANCELLED") else "EXPIRED"
        tx = PaymentTransaction(
            booking_id=uuid.UUID(booking["id"]),
            booking_code=booking["booking_code"],
            amount=Decimal(str(expected_vnd)),
            expected_amount=expected_vnd,
            received_amount=received_vnd,
            refunded_amount=0,
            currency="VND",
            payment_mode=settings.normalized_payment_mode,
            simulation_notice=SIMULATION_NOTICE_VI,
            transfer_content=f"PKB {booking['booking_code']}",
            qr_image_url=build_non_financial_demo_qr(booking["booking_code"], expected_vnd),
            bank_bin="SIMULATED",
            bank_account_no="DEMO-ONLY",
            bank_account_name="THANH TOÁN GIẢ LẬP",
            provider=provider,
            provider_tx_id=provider_tx_id,
            status=tx_status,
            reconciliation_status="COMPENSATION_REQUIRED",
            reconciliation_note=f"Thanh toán trễ khi đơn ở trạng thái {booking['status']}",
            booking_snapshot={"booking_id": booking["id"], "booking_code": booking["booking_code"]},
            expires_at=datetime.fromisoformat(booking["expires_at"]),
            paid_at=now_utc,
        )
        db.add(tx)
        await db.flush()
    else:
        existing_comp = await db.scalar(
            select(PaymentCompensation).where(
                PaymentCompensation.booking_code == booking_code,
                PaymentCompensation.provider_tx_id == provider_tx_id,
            )
        )
        if existing_comp:
            return PaymentResponse.model_validate(tx)
        tx.received_amount = (tx.received_amount or 0) + received_vnd
        tx.reconciliation_status = "COMPENSATION_REQUIRED"
        tx.reconciliation_note = f"Thanh toán trễ khi giao dịch đang ở trạng thái {tx.status}"
        if not tx.provider_tx_id:
            tx.provider_tx_id = provider_tx_id
            tx.provider = provider
            tx.paid_at = now_utc

    expected_vnd = tx.expected_amount or int(round(float(tx.amount)))
    await _record_attempt(
        db,
        tx=tx,
        provider=provider,
        provider_tx_id=provider_tx_id,
        outcome="LATE",
        received_amount=received_vnd,
        failure_reason=f"Late payment received in status {tx.status}",
        initiated_by=initiated_by,
    )
    db.add(
        PaymentCompensation(
            payment_id=tx.id,
            booking_code=booking_code,
            provider=provider,
            provider_tx_id=provider_tx_id,
            amount=Decimal(str(received_vnd)),
            reason=f"LATE_PAYMENT_TX_{tx.status}",
            status="COMPENSATION_REQUIRED",
        )
    )
    await _create_reconciliation_case(
        db,
        payment=tx,
        booking_code=booking_code,
        case_type="LATE_PAYMENT",
        expected_amount=expected_vnd,
        received_amount=received_vnd,
        provider_tx_id=provider_tx_id,
        note=f"Thanh toán trễ ({received_vnd:,} VND) khi đơn/giao dịch ở trạng thái {tx.status}",
        actor=initiated_by,
    )
    enqueue_outbox_event(
        db,
        event_type="payment.compensation_required",
        aggregate_id=booking_code,
        payload={
            "payment_id": str(tx.id),
            "booking_code": booking_code,
            "provider": provider,
            "provider_tx_id": provider_tx_id,
            "amount": received_vnd,
            "reason": f"LATE_PAYMENT_TX_{tx.status}",
        },
    )
    await db.commit()
    await db.refresh(tx)
    PAYMENT_COMPENSATION_REQUIRED_TOTAL.labels(reason="late_payment").inc()
    return PaymentResponse.model_validate(tx)


async def confirm_payment_idempotent(
    db: AsyncSession,
    booking_code: str,
    provider_tx_id: str,
    provider: str = "SIMULATED_GATEWAY",
    amount_paid: int | float | None = None,
    outcome: str = "SUCCEEDED",
    failure_reason: str | None = None,
    initiated_by: str = "webhook",
    payment_method: str = "SIMULATED_ONLINE",
    expected_revision: int | None = None,
) -> PaymentResponse:
    _require_provider()
    code = booking_code.strip()
    tx = await db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.booking_code == code)
        .with_for_update()
    )
    if not tx:
        try:
            await create_or_get_payment(db, code)
        except HTTPException as exc:
            if amount_paid is not None and exc.status_code == status.HTTP_400_BAD_REQUEST:
                booking = await fetch_booking_from_service(code)
                received_vnd = int(round(float(amount_paid)))
                return await _handle_late_payment(
                    db,
                    tx=None,
                    booking=booking,
                    booking_code=code,
                    provider=provider,
                    provider_tx_id=provider_tx_id,
                    received_vnd=received_vnd,
                    initiated_by=initiated_by,
                )
            raise
        tx = await db.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.booking_code == code)
            .with_for_update()
        )
        assert tx is not None

    expected_vnd = tx.expected_amount or int(round(float(tx.amount)))
    received_vnd = int(round(float(amount_paid))) if amount_paid is not None else expected_vnd

    # 0. Idempotent replay check across all prior financial receipts for this payment
    if provider_tx_id:
        prior_receipt = await db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.payment_id == tx.id,
                PaymentAttempt.provider_tx_id == provider_tx_id,
                PaymentAttempt.outcome.in_(("SUCCEEDED", "UNDERPAID", "OVERPAID", "DUPLICATE", "LATE")),
            )
        )
        if prior_receipt:
            return PaymentResponse.model_validate(tx)

    # 1. Already SUCCEEDED -> distinct duplicate payment increments cumulative received_amount & opens reconciliation
    if tx.status == "SUCCEEDED":
        if tx.provider_tx_id == provider_tx_id:
            return PaymentResponse.model_validate(tx)
        # Distinct provider_tx_id after SUCCEEDED -> DUPLICATE_PAYMENT reconciliation case
        tx.received_amount = (tx.received_amount or 0) + received_vnd
        await _record_attempt(
            db,
            tx=tx,
            provider=provider,
            provider_tx_id=provider_tx_id,
            outcome="DUPLICATE",
            received_amount=received_vnd,
            failure_reason=f"Giao dịch trùng lặp với mã {provider_tx_id}",
            initiated_by=initiated_by,
        )
        tx.reconciliation_status = "OPEN"
        tx.reconciliation_note = f"Phát hiện thanh toán trùng lặp ({provider_tx_id})"
        await _create_reconciliation_case(
            db,
            payment=tx,
            booking_code=code,
            case_type="DUPLICATE_PAYMENT",
            expected_amount=expected_vnd,
            received_amount=received_vnd,
            provider_tx_id=provider_tx_id,
            note=f"Thanh toán trùng lặp ngoài giao dịch đã thành công ({tx.provider_tx_id} vs {provider_tx_id})",
            actor=initiated_by,
        )
        _record_audit(
            db,
            entity_type="PAYMENT",
            entity_id=str(tx.id),
            booking_code=code,
            action="PAYMENT_DUPLICATE_RECEIPT",
            actor=initiated_by,
            actor_role="SYSTEM",
            previous_state="SUCCEEDED",
            new_state="SUCCEEDED",
            amount_vnd=received_vnd,
            reason=f"Ghi nhận biên nhận trùng lặp {provider_tx_id} (+{received_vnd:,}đ)",
        )
        await db.commit()
        await db.refresh(tx)
        return PaymentResponse.model_validate(tx)

    # 2. EXPIRED or CANCELLED (or authoritative booking already EXPIRED/CANCELLED) -> Late payment compensation
    if tx.status in ("EXPIRED", "CANCELLED"):
        if amount_paid is not None or outcome == "LATE":
            return await _handle_late_payment(
                db,
                tx=tx,
                booking=None,
                booking_code=code,
                provider=provider,
                provider_tx_id=provider_tx_id,
                received_vnd=received_vnd,
                initiated_by=initiated_by,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Giao dịch đã ở trạng thái {tx.status}, không thể xác nhận thanh toán",
        )

    if outcome == "LATE":
        try:
            auth_booking = await fetch_booking_from_service(code)
            if auth_booking.get("status") in ("EXPIRED", "CANCELLED"):
                tx.status = str(auth_booking["status"])
                return await _handle_late_payment(
                    db,
                    tx=tx,
                    booking=auth_booking,
                    booking_code=code,
                    provider=provider,
                    provider_tx_id=provider_tx_id,
                    received_vnd=received_vnd,
                    initiated_by=initiated_by,
                )
        except HTTPException:
            pass
        return await _handle_late_payment(
            db,
            tx=tx,
            booking=None,
            booking_code=code,
            provider=provider,
            provider_tx_id=provider_tx_id,
            received_vnd=received_vnd,
            initiated_by=initiated_by,
        )

    # 3. Explicitly simulated PROCESSING state
    if outcome == "PROCESSING":
        prev = tx.status
        tx.status = "PROCESSING"
        tx.provider = provider
        tx.failure_reason = None
        await _record_attempt(
            db,
            tx=tx,
            provider=provider,
            provider_tx_id=provider_tx_id,
            outcome="PROCESSING",
            received_amount=0,
            initiated_by=initiated_by,
        )
        _record_audit(
            db,
            entity_type="PAYMENT",
            entity_id=str(tx.id),
            booking_code=code,
            action="PAYMENT_PROCESSING",
            actor=initiated_by,
            actor_role="SYSTEM",
            previous_state=prev,
            new_state="PROCESSING",
            amount_vnd=expected_vnd,
        )
        await db.commit()
        await db.refresh(tx)
        return PaymentResponse.model_validate(tx)

    # 4. Explicitly simulated FAILED state
    if outcome == "FAILED":
        prev = tx.status
        reason = failure_reason or "Thanh toán giả lập thất bại (Insufficient funds / Declined)"
        tx.status = "FAILED"
        tx.provider = provider
        tx.failure_reason = reason
        await _record_attempt(
            db,
            tx=tx,
            provider=provider,
            provider_tx_id=provider_tx_id,
            outcome="FAILED",
            received_amount=0,
            failure_reason=reason,
            initiated_by=initiated_by,
        )
        _record_audit(
            db,
            entity_type="PAYMENT",
            entity_id=str(tx.id),
            booking_code=code,
            action="PAYMENT_FAILED",
            actor=initiated_by,
            actor_role="SYSTEM",
            previous_state=prev,
            new_state="FAILED",
            amount_vnd=expected_vnd,
            reason=reason,
        )
        enqueue_outbox_event(
            db,
            event_type="payment.failed",
            aggregate_id=code,
            payload={
                "payment_id": str(tx.id),
                "booking_code": code,
                "provider": provider,
                "provider_tx_id": provider_tx_id,
                "expected_amount": expected_vnd,
                "reason": reason,
            },
        )
        await db.commit()
        await db.refresh(tx)
        PAYMENTS_FAILED_TOTAL.labels(reason="provider_declined").inc()
        return PaymentResponse.model_validate(tx)

    # 5. Underpayment check (cumulative received vs expected)
    cumulative_received = (tx.received_amount or 0) + received_vnd
    if cumulative_received < expected_vnd:
        prev = tx.status
        shortfall = expected_vnd - cumulative_received
        reason = f"Thanh toán thiếu: đã nhận {cumulative_received:,}đ / cần {expected_vnd:,}đ (thiếu {shortfall:,}đ)"
        tx.status = "FAILED"
        tx.provider = provider
        tx.received_amount = cumulative_received
        tx.failure_reason = reason
        tx.reconciliation_status = "OPEN"
        tx.reconciliation_note = reason
        await _record_attempt(
            db,
            tx=tx,
            provider=provider,
            provider_tx_id=provider_tx_id,
            outcome="UNDERPAID",
            received_amount=received_vnd,
            failure_reason=reason,
            initiated_by=initiated_by,
        )
        await _create_reconciliation_case(
            db,
            payment=tx,
            booking_code=code,
            case_type="UNDERPAYMENT",
            expected_amount=expected_vnd,
            received_amount=cumulative_received,
            provider_tx_id=provider_tx_id,
            note=reason,
            actor=initiated_by,
        )
        enqueue_outbox_event(
            db,
            event_type="payment.failed",
            aggregate_id=code,
            payload={
                "payment_id": str(tx.id),
                "booking_code": code,
                "provider": provider,
                "provider_tx_id": provider_tx_id,
                "expected_amount": expected_vnd,
                "received_amount": cumulative_received,
                "reason": "UNDERPAYMENT",
            },
        )
        await db.commit()
        await db.refresh(tx)
        PAYMENTS_FAILED_TOTAL.labels(reason="underpayment").inc()
        return PaymentResponse.model_validate(tx)

    # 6. Exact or Overpayment -> SUCCEEDED (confirm booking!)
    if expected_revision is not None and tx.booking_revision != expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Phiên bản đơn đặt sân không khớp (hiện tại v{tx.booking_revision} != v{expected_revision})",
        )
    prev = tx.status
    now_utc = datetime.now(timezone.utc)
    tx.status = "SUCCEEDED"
    tx.provider = provider
    tx.payment_method = payment_method
    tx.provider_tx_id = provider_tx_id
    tx.received_amount = cumulative_received
    tx.failure_reason = None
    tx.paid_at = now_utc
    if payment_method == "SIMULATED_CASH":
        tx.collected_by = initiated_by
        tx.collected_at = now_utc

    is_overpaid = cumulative_received > expected_vnd
    attempt_outcome = "OVERPAID" if is_overpaid else "SUCCEEDED"
    await _record_attempt(
        db,
        tx=tx,
        provider=provider,
        payment_method=payment_method,
        provider_tx_id=provider_tx_id,
        outcome=attempt_outcome,
        received_amount=received_vnd,
        initiated_by=initiated_by,
    )

    if is_overpaid:
        excess = cumulative_received - expected_vnd
        note = f"Thanh toán dư {excess:,}đ (nhận {cumulative_received:,}đ / đơn {expected_vnd:,}đ)"
        tx.reconciliation_status = "OPEN"
        tx.reconciliation_note = note
        await _create_reconciliation_case(
            db,
            payment=tx,
            booking_code=code,
            case_type="OVERPAYMENT",
            expected_amount=expected_vnd,
            received_amount=cumulative_received,
            provider_tx_id=provider_tx_id,
            note=note,
            actor=initiated_by,
        )

    _record_audit(
        db,
        entity_type="PAYMENT",
        entity_id=str(tx.id),
        booking_code=code,
        action="PAYMENT_SUCCEEDED",
        actor=initiated_by,
        actor_role="SYSTEM",
        previous_state=prev,
        new_state="SUCCEEDED",
        amount_vnd=cumulative_received,
        reason="Xác nhận thanh toán giả lập thành công" + (" (có dư tiền)" if is_overpaid else ""),
        metadata={"provider": provider, "provider_tx_id": provider_tx_id},
    )

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
            "expected_amount": expected_vnd,
            "received_amount": cumulative_received,
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


async def collect_simulated_cash(
    db: AsyncSession,
    *,
    booking_code: str,
    amount: int,
    idempotency_key: str,
    staff_email: str,
    note: str | None = None,
) -> PaymentResponse:
    _require_provider()
    code = booking_code.strip()
    provider_tx_id = f"CASH-{idempotency_key.strip()}"

    # Check idempotency first before querying booking-service if already recorded
    existing_attempt = await db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.booking_code == code,
            PaymentAttempt.provider_tx_id == provider_tx_id,
        )
    )
    if existing_attempt:
        tx = await db.scalar(select(PaymentTransaction).where(PaymentTransaction.booking_code == code))
        if tx:
            return PaymentResponse.model_validate(tx)

    booking = await fetch_booking_from_service(code)
    if booking["status"] in ("CANCELLED", "EXPIRED"):
        # Still record late payment compensation if staff collected cash against cancelled/expired booking
        return await confirm_payment_idempotent(
            db=db,
            booking_code=code,
            provider_tx_id=provider_tx_id,
            provider="SIMULATED_COUNTER",
            payment_method="SIMULATED_CASH",
            amount_paid=amount,
            outcome="LATE",
            initiated_by=staff_email,
        )
    if booking["status"] != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đơn đặt sân đang ở trạng thái {booking['status']}, không thể thu tiền mặt giả lập",
        )

    expected_amount = int(round(float(booking["total_amount"])))
    if amount != expected_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Số tiền thu tại quầy ({amount:,}đ) không khớp tổng tiền đơn ({expected_amount:,}đ)",
        )
    await create_or_get_payment(db, code)
    res = await confirm_payment_idempotent(
        db=db,
        booking_code=code,
        provider_tx_id=provider_tx_id,
        provider="SIMULATED_COUNTER",
        payment_method="SIMULATED_CASH",
        amount_paid=amount,
        outcome="SUCCEEDED",
        initiated_by=staff_email,
        expected_revision=int(booking.get("booking_revision") or 1),
    )
    CASH_COLLECTIONS_TOTAL.labels(outcome=res.status).inc()
    return res


async def sync_payment_revision(
    db: AsyncSession,
    *,
    booking_code: str,
    expected_amount: int,
    booking_revision: int,
) -> dict:
    tx = await db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.booking_code == booking_code.strip())
        .with_for_update()
    )
    if not tx:
        return {"updated": False}
    if tx.booking_revision >= booking_revision:
        return {
            "updated": False,
            "stale": tx.booking_revision > booking_revision,
            "booking_revision": tx.booking_revision,
            "expected_amount": tx.expected_amount,
        }
    if tx.status == "SUCCEEDED":
        tx.booking_revision = booking_revision
        await db.commit()
        return {"updated": True, "status": tx.status}

    prev_amount = tx.expected_amount
    tx.expected_amount = expected_amount
    tx.amount = Decimal(str(expected_amount))
    tx.booking_revision = booking_revision
    tx.qr_image_url = build_non_financial_demo_qr(tx.booking_code, expected_amount)
    if tx.status in ("FAILED", "PROCESSING"):
        tx.status = "PENDING"
        tx.failure_reason = None
    _record_audit(
        db,
        entity_type="PAYMENT",
        entity_id=str(tx.id),
        booking_code=tx.booking_code,
        action="PAYMENT_REVISION_SYNCED",
        actor="court-booking-service",
        actor_role="SYSTEM",
        previous_state=f"amt={prev_amount}",
        new_state=f"amt={expected_amount},rev={booking_revision}",
        amount_vnd=expected_amount,
        reason="Cập nhật nghĩa vụ thanh toán theo lịch đặt sân mới",
    )
    await db.commit()
    return {"updated": True, "expected_amount": expected_amount, "booking_revision": booking_revision}


async def check_reschedule_eligibility(db: AsyncSession, booking_code: str) -> dict:
    code = booking_code.strip()
    tx = await db.scalar(select(PaymentTransaction).where(PaymentTransaction.booking_code == code))
    if not tx:
        return {"blocked": False, "reason": None}
    if tx.reconciliation_status in ("OPEN", "IN_REVIEW", "COMPENSATION_REQUIRED"):
        return {
            "blocked": True,
            "reason": f"Đơn đang có hồ sơ đối soát ({tx.reconciliation_status}), không thể đổi lịch",
        }
    active_refund = await db.scalar(
        select(RefundTransaction).where(
            RefundTransaction.booking_code == code,
            RefundTransaction.status.in_(("REQUESTED", "APPROVED", "PROCESSING", "SUCCEEDED")),
        )
    )
    if active_refund:
        return {
            "blocked": True,
            "reason": f"Đơn đã có giao dịch hoàn tiền ({active_refund.status}), không thể đổi lịch",
        }
    return {"blocked": False, "reason": None}


async def retry_failed_payment(
    db: AsyncSession,
    booking_code: str,
    actor: str = "customer",
) -> PaymentResponse:
    _require_provider()
    code = booking_code.strip()
    tx = await db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.booking_code == code)
        .with_for_update()
    )
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy giao dịch")
    if tx.status != "FAILED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ có thể thử lại khi giao dịch ở trạng thái FAILED (hiện tại: {tx.status})",
        )
    if tx.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên thanh toán đã hết hạn, vui lòng đặt lại sân",
        )
    prev = tx.status
    tx.status = "PENDING"
    tx.failure_reason = None
    _record_audit(
        db,
        entity_type="PAYMENT",
        entity_id=str(tx.id),
        booking_code=code,
        action="PAYMENT_RETRY_INITIATED",
        actor=actor,
        actor_role="USER",
        previous_state=prev,
        new_state="PENDING",
        amount_vnd=tx.expected_amount,
        reason="Người dùng khởi tạo lại phiên thanh toán",
    )
    await db.commit()
    await db.refresh(tx)
    return PaymentResponse.model_validate(tx)


async def simulate_payment_outcome(
    db: AsyncSession,
    *,
    booking_code: str,
    outcome: str,
    amount: int | None = None,
    provider_tx_id: str | None = None,
    failure_reason: str | None = None,
    actor: str = "simulator",
) -> PaymentResponse:
    _require_provider()
    code = booking_code.strip()
    tx_id = provider_tx_id or f"SIM-{uuid.uuid4().hex[:8].upper()}"

    # Ensure payment exists unless LATE on expired/cancelled booking
    tx = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.booking_code == code)
    )
    expected_vnd = tx.expected_amount if tx else None
    if expected_vnd is None:
        booking = await fetch_booking_from_service(code)
        expected_vnd = int(round(float(booking["total_amount"])))

    if outcome == "UNDERPAID":
        sim_amount = amount if amount is not None else max(1000, expected_vnd // 2)
        if sim_amount >= expected_vnd:
            raise HTTPException(status_code=400, detail="Số tiền UNDERPAID phải nhỏ hơn số tiền cần thanh toán")
        mapped_outcome = "SUCCEEDED"
    elif outcome == "OVERPAID":
        sim_amount = amount if amount is not None else expected_vnd + 50000
        if sim_amount <= expected_vnd:
            raise HTTPException(status_code=400, detail="Số tiền OVERPAID phải lớn hơn số tiền cần thanh toán")
        mapped_outcome = "SUCCEEDED"
    elif outcome == "LATE":
        sim_amount = amount if amount is not None else expected_vnd
        mapped_outcome = "LATE"
    elif outcome == "DUPLICATE":
        sim_amount = amount if amount is not None else expected_vnd
        mapped_outcome = "SUCCEEDED"
    else:
        sim_amount = amount if amount is not None else expected_vnd
        mapped_outcome = outcome

    return await confirm_payment_idempotent(
        db=db,
        booking_code=code,
        provider_tx_id=tx_id,
        provider="SIMULATED_GATEWAY",
        amount_paid=sim_amount,
        outcome=mapped_outcome,
        failure_reason=failure_reason,
        initiated_by=actor,
    )


async def update_reconciliation_case(
    db: AsyncSession,
    *,
    case_id: uuid.UUID,
    new_status: str,
    resolution_action: str | None,
    resolution_note: str,
    actor_email: str,
) -> ReconciliationCaseResponse:
    case = await db.scalar(
        select(ReconciliationCase)
        .where(ReconciliationCase.id == case_id)
        .with_for_update()
    )
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ đối soát")
    if case.status == "RESOLVED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hồ sơ đối soát đã được đóng")

    prev = case.status
    now_utc = datetime.now(timezone.utc)
    if new_status == "RESOLVED":
        refund_actions = {"REFUNDED_EXCESS", "REFUNDED_DUPLICATE", "REFUNDED_LATE", "REFUNDED_COMPENSATION"}
        non_refund_actions = {"TOP_UP_COMPLETED", "MANUAL_WRITE_OFF", "NO_FINANCIAL_IMPACT"}
        action = (resolution_action or "").strip().upper()
        if action not in refund_actions and action not in non_refund_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hành động đối soát (resolution_action) không hợp lệ khi đóng hồ sơ",
            )
        if action in refund_actions:
            succeeded_refunded = await db.scalar(
                select(func.coalesce(func.sum(RefundTransaction.refunded_amount), 0)).where(
                    RefundTransaction.booking_code == case.booking_code,
                    RefundTransaction.status == "SUCCEEDED",
                )
            )
            required_refund = (
                case.received_amount
                if case.case_type in ("LATE_PAYMENT", "CONFIRMATION_FAILED", "DUPLICATE_PAYMENT")
                else abs(case.discrepancy_amount)
            )
            if int(succeeded_refunded or 0) <= 0 or int(succeeded_refunded or 0) < required_refund:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Chưa có giao dịch hoàn tiền SUCCEEDED đủ số tiền ({int(succeeded_refunded or 0):,}đ / cần {required_refund:,}đ) để đóng đối soát",
                )
        elif action == "TOP_UP_COMPLETED":
            tx_check = await db.scalar(
                select(PaymentTransaction).where(PaymentTransaction.booking_code == case.booking_code)
            )
            if not tx_check or tx_check.status != "SUCCEEDED" or tx_check.received_amount < tx_check.expected_amount:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Chưa nhận đủ số tiền thanh toán để đóng đối soát theo hướng TOP_UP_COMPLETED",
                )
        elif len((resolution_note or "").strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đóng đối soát không hoàn tiền bắt buộc ghi rõ lý do (>= 10 ký tự)",
            )
        resolution_action = action

    case.status = new_status
    case.resolution_action = resolution_action
    case.resolution_note = resolution_note
    case.updated_at = now_utc
    if new_status == "RESOLVED":
        case.resolved_by = actor_email
        case.resolved_at = now_utc

    if case.payment_id:
        tx = await db.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.id == case.payment_id)
            .with_for_update()
        )
        if tx:
            open_others = await db.scalar(
                select(func.count(ReconciliationCase.id)).where(
                    ReconciliationCase.payment_id == tx.id,
                    ReconciliationCase.id != case.id,
                    ReconciliationCase.status != "RESOLVED",
                )
            )
            if new_status == "RESOLVED" and (open_others or 0) == 0:
                tx.reconciliation_status = "RESOLVED"
                tx.reconciliation_note = resolution_note
            elif new_status == "IN_REVIEW":
                tx.reconciliation_status = "IN_REVIEW"

    _record_audit(
        db,
        entity_type="RECONCILIATION",
        entity_id=str(case.id),
        booking_code=case.booking_code,
        action=f"RECONCILIATION_{new_status}",
        actor=actor_email,
        actor_role="ADMIN",
        previous_state=prev,
        new_state=new_status,
        amount_vnd=abs(case.discrepancy_amount),
        reason=resolution_note,
        metadata={"resolution_action": resolution_action},
    )
    await db.commit()
    await db.refresh(case)
    return ReconciliationCaseResponse.model_validate(case)


async def create_refund_request(
    db: AsyncSession,
    *,
    booking_code: str,
    requested_amount: int,
    policy_tier: str,
    policy_percent: int,
    reason: str,
    requested_by: str,
    actor_role: str = "USER",
    admin_override_reason: str | None = None,
    auto_approve: bool = False,
) -> RefundResponse:
    code = booking_code.strip()
    tx = await db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.booking_code == code)
        .with_for_update()
    )
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy giao dịch thanh toán")
    if tx.status != "SUCCEEDED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ có thể hoàn tiền cho giao dịch SUCCEEDED (hiện tại: {tx.status})",
        )

    expected_vnd = tx.expected_amount or int(round(float(tx.amount)))
    paid_cap = tx.received_amount if tx.received_amount > 0 else expected_vnd

    # Policy entitlement enforcement (prevent ordinary cancellation from exceeding policy entitlement)
    if policy_tier in ("FULL_24H", "PARTIAL_2H_24H", "NON_REFUNDABLE_LT_2H"):
        max_policy_amount = int(round(expected_vnd * policy_percent / 100))
        if requested_amount > max_policy_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số tiền hoàn ({requested_amount:,}đ) vượt quá mức chính sách {policy_tier} ({max_policy_amount:,}đ)",
            )
    elif policy_tier == "OVERPAYMENT_EXCESS":
        excess_cap = max(0, paid_cap - expected_vnd)
        if requested_amount > excess_cap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Số tiền hoàn phần dư ({requested_amount:,}đ) vượt quá phần thu dư thực tế ({excess_cap:,}đ)",
            )
    elif policy_tier == "ADMIN_EXCEPTION" and not (admin_override_reason or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hoàn tiền ngoại lệ ADMIN_EXCEPTION bắt buộc có admin_override_reason",
        )

    # Concurrency-safe over-refund check under row lock on PaymentTransaction
    committed_or_pending = await db.scalar(
        select(func.coalesce(func.sum(RefundTransaction.requested_amount), 0)).where(
            RefundTransaction.payment_id == tx.id,
            RefundTransaction.status.in_(("REQUESTED", "APPROVED", "PROCESSING", "SUCCEEDED")),
        )
    )
    total_after = int(committed_or_pending or 0) + requested_amount
    if total_after > paid_cap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tổng tiền hoàn ({total_after:,}đ) vượt quá số tiền đã thanh toán ({paid_cap:,}đ)",
        )

    now_utc = datetime.now(timezone.utc)
    refund_code = f"RF-{code}-{uuid.uuid4().hex[:6].upper()}"
    initial_status = "APPROVED" if auto_approve else "REQUESTED"
    refund = RefundTransaction(
        payment_id=tx.id,
        booking_id=tx.booking_id,
        booking_code=code,
        refund_code=refund_code,
        original_paid_amount=paid_cap,
        requested_amount=requested_amount,
        approved_amount=requested_amount if auto_approve else 0,
        refunded_amount=0,
        policy_tier=policy_tier,
        policy_percent=policy_percent,
        status=initial_status,
        reason=reason,
        admin_override_reason=admin_override_reason,
        provider="SIMULATED_GATEWAY",
        requested_by=requested_by,
        approved_by=requested_by if auto_approve else None,
        approved_at=now_utc if auto_approve else None,
    )
    db.add(refund)
    await db.flush()

    _record_audit(
        db,
        entity_type="REFUND",
        entity_id=str(refund.id),
        booking_code=code,
        action="REFUND_REQUESTED",
        actor=requested_by,
        actor_role=actor_role,
        previous_state=None,
        new_state=initial_status,
        amount_vnd=requested_amount,
        reason=reason,
        metadata={"policy_tier": policy_tier, "policy_percent": policy_percent},
    )
    enqueue_outbox_event(
        db,
        event_type="refund.requested",
        aggregate_id=code,
        payload={
            "refund_id": str(refund.id),
            "refund_code": refund.refund_code,
            "booking_code": code,
            "requested_amount": requested_amount,
            "policy_tier": policy_tier,
            "status": initial_status,
        },
    )
    await db.commit()
    await db.refresh(refund)
    REFUNDS_TOTAL.labels(status=initial_status, policy_tier=policy_tier).inc()
    return RefundResponse.model_validate(refund)


async def approve_refund(
    db: AsyncSession,
    *,
    refund_id: uuid.UUID,
    admin_email: str,
    approved_amount: int | None = None,
    note: str | None = None,
) -> RefundResponse:
    refund = await db.scalar(
        select(RefundTransaction).where(RefundTransaction.id == refund_id).with_for_update()
    )
    if not refund:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoàn tiền")
    if refund.status != "REQUESTED":
        raise HTTPException(status_code=400, detail=f"Không thể duyệt hoàn tiền ở trạng thái {refund.status}")

    tx = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.id == refund.payment_id).with_for_update()
    )
    assert tx is not None
    final_amount = approved_amount if approved_amount is not None else refund.requested_amount
    if final_amount > refund.original_paid_amount:
        raise HTTPException(status_code=409, detail="Số tiền duyệt vượt quá số tiền đã thanh toán")

    other_active = await db.scalar(
        select(func.coalesce(func.sum(RefundTransaction.requested_amount), 0)).where(
            RefundTransaction.payment_id == tx.id,
            RefundTransaction.id != refund.id,
            RefundTransaction.status.in_(("REQUESTED", "APPROVED", "PROCESSING", "SUCCEEDED")),
        )
    )
    if int(other_active or 0) + final_amount > refund.original_paid_amount:
        raise HTTPException(status_code=409, detail="Tổng số tiền hoàn vượt quá số tiền đã thanh toán")

    now_utc = datetime.now(timezone.utc)
    refund.status = "APPROVED"
    refund.approved_amount = final_amount
    refund.approved_by = admin_email
    refund.approved_at = now_utc
    refund.updated_at = now_utc

    _record_audit(
        db,
        entity_type="REFUND",
        entity_id=str(refund.id),
        booking_code=refund.booking_code,
        action="REFUND_APPROVED",
        actor=admin_email,
        actor_role="ADMIN",
        previous_state="REQUESTED",
        new_state="APPROVED",
        amount_vnd=final_amount,
        reason=note or refund.reason,
    )
    await db.commit()
    await db.refresh(refund)
    REFUNDS_TOTAL.labels(status="APPROVED", policy_tier=refund.policy_tier).inc()
    return RefundResponse.model_validate(refund)


async def reject_refund(
    db: AsyncSession,
    *,
    refund_id: uuid.UUID,
    admin_email: str,
    rejection_reason: str,
) -> RefundResponse:
    refund = await db.scalar(
        select(RefundTransaction).where(RefundTransaction.id == refund_id).with_for_update()
    )
    if not refund:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoàn tiền")
    if refund.status not in ("REQUESTED", "APPROVED"):
        raise HTTPException(status_code=400, detail=f"Không thể từ chối hoàn tiền ở trạng thái {refund.status}")

    prev = refund.status
    now_utc = datetime.now(timezone.utc)
    refund.status = "REJECTED"
    refund.rejection_reason = rejection_reason
    refund.approved_by = admin_email
    refund.updated_at = now_utc

    _record_audit(
        db,
        entity_type="REFUND",
        entity_id=str(refund.id),
        booking_code=refund.booking_code,
        action="REFUND_REJECTED",
        actor=admin_email,
        actor_role="ADMIN",
        previous_state=prev,
        new_state="REJECTED",
        amount_vnd=refund.requested_amount,
        reason=rejection_reason,
    )
    await db.commit()
    await db.refresh(refund)
    REFUNDS_TOTAL.labels(status="REJECTED", policy_tier=refund.policy_tier).inc()
    return RefundResponse.model_validate(refund)


async def execute_refund(
    db: AsyncSession,
    *,
    refund_id: uuid.UUID,
    admin_email: str,
    outcome: str = "SUCCEEDED",
    failure_reason: str | None = None,
) -> RefundResponse:
    provider = _require_provider()
    refund = await db.scalar(
        select(RefundTransaction).where(RefundTransaction.id == refund_id).with_for_update()
    )
    if not refund:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoàn tiền")
    if refund.status == "SUCCEEDED":
        return RefundResponse.model_validate(refund)
    if refund.status not in ("APPROVED", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ có thể thực thi hoàn tiền từ trạng thái APPROVED hoặc FAILED (hiện tại: {refund.status})",
        )

    tx = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.id == refund.payment_id).with_for_update()
    )
    assert tx is not None

    prev = refund.status
    if prev == "FAILED":
        refund.retry_count = (refund.retry_count or 0) + 1

    exec_amount = refund.approved_amount or refund.requested_amount
    # Double-check over-refund cap at execution time
    already_succeeded = await db.scalar(
        select(func.coalesce(func.sum(RefundTransaction.refunded_amount), 0)).where(
            RefundTransaction.payment_id == tx.id,
            RefundTransaction.id != refund.id,
            RefundTransaction.status == "SUCCEEDED",
        )
    )
    paid_cap = tx.received_amount if tx.received_amount > 0 else (tx.expected_amount or int(round(float(tx.amount))))
    if int(already_succeeded or 0) + exec_amount > paid_cap:
        raise HTTPException(status_code=409, detail="Tổng số tiền đã hoàn vượt quá số tiền đã thu")

    result = provider.execute_refund(
        refund_code=refund.refund_code,
        booking_code=refund.booking_code,
        amount_vnd=exec_amount,
        outcome=outcome,
    )
    now_utc = datetime.now(timezone.utc)
    refund.provider_refund_id = result.provider_refund_id
    refund.processed_by = admin_email
    refund.updated_at = now_utc

    if result.status == "SUCCEEDED":
        refund.status = "SUCCEEDED"
        refund.refunded_amount = exec_amount
        refund.failure_reason = None
        refund.completed_at = now_utc
        tx.refunded_amount = int(already_succeeded or 0) + exec_amount
        enqueue_outbox_event(
            db,
            event_type="refund.succeeded",
            aggregate_id=refund.booking_code,
            payload={
                "refund_id": str(refund.id),
                "refund_code": refund.refund_code,
                "booking_code": refund.booking_code,
                "refunded_amount": exec_amount,
                "provider_refund_id": result.provider_refund_id,
                "customer_email": (tx.booking_snapshot or {}).get("customer_email", ""),
                "customer_name": (tx.booking_snapshot or {}).get("customer_name", ""),
            },
        )
    elif result.status == "FAILED":
        refund.status = "FAILED"
        refund.failure_reason = failure_reason or result.message
        enqueue_outbox_event(
            db,
            event_type="refund.failed",
            aggregate_id=refund.booking_code,
            payload={
                "refund_id": str(refund.id),
                "refund_code": refund.refund_code,
                "booking_code": refund.booking_code,
                "requested_amount": exec_amount,
                "reason": refund.failure_reason,
            },
        )
    else:
        refund.status = "PROCESSING"
        refund.failure_reason = None

    _record_audit(
        db,
        entity_type="REFUND",
        entity_id=str(refund.id),
        booking_code=refund.booking_code,
        action=f"REFUND_{refund.status}",
        actor=admin_email,
        actor_role="ADMIN",
        previous_state=prev,
        new_state=refund.status,
        amount_vnd=exec_amount,
        reason=refund.failure_reason or result.message,
        metadata={"provider_refund_id": result.provider_refund_id},
    )
    await db.commit()
    await db.refresh(refund)
    REFUNDS_TOTAL.labels(status=refund.status, policy_tier=refund.policy_tier).inc()
    return RefundResponse.model_validate(refund)


async def process_refund_callback(
    db: AsyncSession,
    *,
    refund_code: str,
    provider_refund_id: str,
    outcome: str,
    failure_reason: str | None = None,
) -> RefundResponse:
    refund = await db.scalar(
        select(RefundTransaction).where(RefundTransaction.refund_code == refund_code).with_for_update()
    )
    if not refund:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch hoàn tiền")
    if refund.provider_refund_id and refund.provider_refund_id != provider_refund_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mã provider_refund_id không khớp với giao dịch hoàn tiền",
        )
    if refund.status == "SUCCEEDED" and outcome == "SUCCEEDED":
        return RefundResponse.model_validate(refund)
    if refund.status not in ("PROCESSING", "APPROVED"):
        raise HTTPException(status_code=400, detail=f"Không thể xử lý callback cho hoàn tiền ở trạng thái {refund.status}")

    tx = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.id == refund.payment_id).with_for_update()
    )
    assert tx is not None
    prev = refund.status
    now_utc = datetime.now(timezone.utc)
    exec_amount = refund.approved_amount or refund.requested_amount
    refund.provider_refund_id = provider_refund_id
    refund.updated_at = now_utc

    if outcome == "SUCCEEDED":
        already_succeeded = await db.scalar(
            select(func.coalesce(func.sum(RefundTransaction.refunded_amount), 0)).where(
                RefundTransaction.payment_id == tx.id,
                RefundTransaction.id != refund.id,
                RefundTransaction.status == "SUCCEEDED",
            )
        )
        paid_cap = tx.received_amount if tx.received_amount > 0 else (tx.expected_amount or int(round(float(tx.amount))))
        if int(already_succeeded or 0) + exec_amount > paid_cap:
            raise HTTPException(status_code=409, detail="Tổng số tiền đã hoàn vượt quá số tiền đã thu")
        refund.status = "SUCCEEDED"
        refund.refunded_amount = exec_amount
        refund.completed_at = now_utc
        refund.failure_reason = None
        tx.refunded_amount = int(already_succeeded or 0) + exec_amount
        enqueue_outbox_event(
            db,
            event_type="refund.succeeded",
            aggregate_id=refund.booking_code,
            payload={
                "refund_id": str(refund.id),
                "refund_code": refund.refund_code,
                "booking_code": refund.booking_code,
                "refunded_amount": exec_amount,
                "provider_refund_id": provider_refund_id,
                "customer_email": (tx.booking_snapshot or {}).get("customer_email", ""),
                "customer_name": (tx.booking_snapshot or {}).get("customer_name", ""),
            },
        )
    else:
        refund.status = "FAILED"
        refund.failure_reason = failure_reason or "Callback hoàn tiền thất bại"
        enqueue_outbox_event(
            db,
            event_type="refund.failed",
            aggregate_id=refund.booking_code,
            payload={
                "refund_id": str(refund.id),
                "refund_code": refund.refund_code,
                "booking_code": refund.booking_code,
                "requested_amount": exec_amount,
                "reason": refund.failure_reason,
            },
        )

    _record_audit(
        db,
        entity_type="REFUND",
        entity_id=str(refund.id),
        booking_code=refund.booking_code,
        action=f"REFUND_CALLBACK_{refund.status}",
        actor="webhook_callback",
        actor_role="SYSTEM",
        previous_state=prev,
        new_state=refund.status,
        amount_vnd=exec_amount,
        reason=refund.failure_reason,
    )
    await db.commit()
    await db.refresh(refund)
    REFUNDS_TOTAL.labels(status=refund.status, policy_tier=refund.policy_tier).inc()
    return RefundResponse.model_validate(refund)


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
            if tx and tx.status in ("PENDING", "PROCESSING", "FAILED"):
                prev = tx.status
                tx.status = "EXPIRED" if event_name == "booking.expired" else "CANCELLED"
                _record_audit(
                    db,
                    entity_type="PAYMENT",
                    entity_id=str(tx.id),
                    booking_code=booking_code,
                    action=f"PAYMENT_{tx.status}_BY_BOOKING_EVENT",
                    actor="rabbitmq",
                    actor_role="SYSTEM",
                    previous_state=prev,
                    new_state=tx.status,
                    amount_vnd=tx.expected_amount,
                    reason=str(data.get("reason") or event_name),
                )
                logger.info("Updated payment %s to %s", booking_code, tx.status)
            elif tx and tx.status == "SUCCEEDED" and event_name == "booking.cancelled":
                refund_amount = int(data.get("refund_amount_vnd") or 0)
                policy_tier = str(data.get("policy_tier") or "FULL_24H")
                policy_percent = int(data.get("policy_percent") or 0)
                if refund_amount > 0:
                    existing_refund = await db.scalar(
                        select(RefundTransaction).where(
                            RefundTransaction.booking_code == booking_code,
                            RefundTransaction.status.in_(("REQUESTED", "APPROVED", "PROCESSING", "SUCCEEDED")),
                        )
                    )
                    if not existing_refund:
                        refund = RefundTransaction(
                            payment_id=tx.id,
                            booking_id=tx.booking_id,
                            booking_code=booking_code,
                            refund_code=f"RF-{booking_code}-{uuid.uuid4().hex[:6].upper()}",
                            original_paid_amount=tx.received_amount or tx.expected_amount,
                            requested_amount=refund_amount,
                            approved_amount=0,
                            refunded_amount=0,
                            policy_tier=policy_tier,
                            policy_percent=policy_percent,
                            status="REQUESTED",
                            reason=str(data.get("reason") or "Hủy đơn đặt sân đã thanh toán"),
                            admin_override_reason=data.get("admin_override_reason"),
                            requested_by=str(data.get("cancelled_by") or "customer"),
                        )
                        db.add(refund)
                        await db.flush()
                        _record_audit(
                            db,
                            entity_type="REFUND",
                            entity_id=str(refund.id),
                            booking_code=booking_code,
                            action="REFUND_REQUESTED_BY_CANCELLATION",
                            actor=str(data.get("cancelled_by") or "customer"),
                            actor_role="SYSTEM",
                            previous_state=None,
                            new_state="REQUESTED",
                            amount_vnd=refund_amount,
                            reason=refund.reason,
                            metadata={"policy_tier": policy_tier, "policy_percent": policy_percent},
                        )
                        enqueue_outbox_event(
                            db,
                            event_type="refund.requested",
                            aggregate_id=booking_code,
                            payload={
                                "refund_id": str(refund.id),
                                "refund_code": refund.refund_code,
                                "booking_code": booking_code,
                                "requested_amount": refund_amount,
                                "policy_tier": policy_tier,
                                "status": "REQUESTED",
                            },
                        )
                        REFUNDS_TOTAL.labels(status="REQUESTED", policy_tier=policy_tier).inc()
        elif event_name == "booking.rescheduled":
            new_rev = int(data.get("new_revision") or 1)
            new_amt = int(round(float(data.get("total_amount") or 0)))
            if tx and tx.booking_revision < new_rev:
                prev_amt = tx.expected_amount
                tx.booking_revision = new_rev
                if tx.status != "SUCCEEDED":
                    tx.expected_amount = new_amt
                    tx.amount = Decimal(str(new_amt))
                    tx.qr_image_url = build_non_financial_demo_qr(tx.booking_code, new_amt)
                    if tx.status in ("FAILED", "PROCESSING"):
                        tx.status = "PENDING"
                        tx.failure_reason = None
                _record_audit(
                    db,
                    entity_type="PAYMENT",
                    entity_id=str(tx.id),
                    booking_code=booking_code,
                    action="PAYMENT_REVISION_SYNCED_EVENT",
                    actor="rabbitmq",
                    actor_role="SYSTEM",
                    previous_state=f"amt={prev_amt}",
                    new_state=f"amt={tx.expected_amount},rev={new_rev}",
                    amount_vnd=tx.expected_amount,
                    reason="Đồng bộ phiên bản lịch từ sự kiện booking.rescheduled",
                )
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
                        provider=tx.provider if tx else "SIMULATED_GATEWAY",
                        provider_tx_id=provider_tx_id,
                        amount=tx.amount if tx else Decimal(str(data.get("total_amount", 0))),
                        reason=reason,
                        status="COMPENSATION_REQUIRED",
                    )
                )
            expected_vnd = tx.expected_amount if tx else int(round(float(data.get("total_amount", 0))))
            received_vnd = tx.received_amount if tx else expected_vnd
            await _create_reconciliation_case(
                db,
                payment=tx,
                booking_code=booking_code,
                case_type="CONFIRMATION_FAILED",
                expected_amount=expected_vnd,
                received_amount=received_vnd,
                provider_tx_id=provider_tx_id,
                note=reason,
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
    await queue.bind(rmq_client.exchange, routing_key="booking.rescheduled")
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
                EVENTS_RETRY_TOTAL.labels(service=settings.service_name, event_type=event_name).inc()
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
                    EVENTS_DLQ_TOTAL.labels(service=settings.service_name, event_type=event_name).inc()
                    await message.reject(requeue=False)

    await queue.consume(_on_message)
