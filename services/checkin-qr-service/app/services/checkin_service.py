import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import aio_pika
import httpx
import qrcode
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    QR_SCANS_TOTAL,
)
from app.models import CancelledBooking, CheckinTicket
from app.schemas import ScanQRResponse, TicketResponse

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def sign_qr_payload(ticket_id: uuid.UUID, booking_code: str, revision: int = 1) -> tuple[str, str]:
    msg = f"{ticket_id}:{booking_code}" if revision <= 1 else f"{ticket_id}:{booking_code}:r{revision}"
    sig = hmac.new(
        settings.qr_hmac_secret.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]
    payload = f"PKB1.{ticket_id}.{booking_code}.{sig}" if revision <= 1 else f"PKB1.{ticket_id}.{booking_code}.r{revision}.{sig}"
    return payload, sig


def generate_qr_base64(qr_payload: str) -> str:
    img = qrcode.make(qr_payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


async def issue_ticket_from_booking_confirmed(event_data: dict) -> None:
    booking_code = str(event_data["booking_code"]).strip()
    event_id = resolve_event_id(
        event_data,
        f"booking.confirmed:{booking_code}:{event_data.get('booking_id', '')}",
    )
    correlation_id = str(event_data.get("correlation_id") or event_id)

    async with AsyncSessionLocal() as db:
        claimed = await claim_inbox_event(
            db,
            consumer_name="checkin-qr-service.booking_confirmed",
            event_id=event_id,
            event_type="booking.confirmed",
            correlation_id=correlation_id,
        )
        if not claimed:
            EVENTS_DUPLICATE_TOTAL.labels(
                service=settings.service_name, event_type="booking.confirmed"
            ).inc()
            logger.info("Duplicate booking.confirmed skipped event_id=%s booking_code=%s", event_id, booking_code)
            return

        cancelled = await db.scalar(
            select(CancelledBooking).where(CancelledBooking.booking_code == booking_code)
        )
        if cancelled:
            await db.commit()
            logger.info(
                "Booking %s already cancelled before ticket issuance; skipping ticket creation",
                booking_code,
            )
            return

        existing = await db.scalar(
            select(CheckinTicket)
            .where(CheckinTicket.booking_code == booking_code)
            .with_for_update()
        )
        if existing:
            # Never recreate or reactivate an existing or REVOKED ticket
            await db.commit()
            logger.info(
                "Ticket already exists (status=%s) for booking_code=%s; skipping issuance",
                existing.status,
                booking_code,
            )
            return

        ticket_id = uuid.uuid4()
        incoming_rev = int(event_data.get("booking_revision") or 1)
        qr_payload, qr_sig = sign_qr_payload(ticket_id, booking_code, incoming_rev)

        play_date_raw = event_data["play_date"]
        play_date = play_date_raw if isinstance(play_date_raw, date) else date.fromisoformat(str(play_date_raw))

        ticket = CheckinTicket(
            id=ticket_id,
            booking_id=uuid.UUID(str(event_data["booking_id"])),
            booking_code=booking_code,
            customer_name=event_data["customer_name"],
            customer_email=event_data["customer_email"],
            customer_phone=event_data.get("customer_phone", ""),
            court_name=event_data["court_name"],
            branch_name=event_data.get("branch_name", ""),
            location_name=event_data.get("location_name", ""),
            location_address=event_data.get("location_address", ""),
            play_date=play_date,
            start_hour=int(event_data["start_hour"]),
            end_hour=int(event_data["end_hour"]),
            total_amount=Decimal(str(event_data.get("total_amount", 0))),
            qr_payload=qr_payload,
            qr_signature=qr_sig,
            booking_revision=incoming_rev,
            status="VALID",
        )
        db.add(ticket)

        enqueue_outbox_event(
            db,
            event_type="ticket.issued",
            aggregate_id=ticket.booking_code,
            correlation_id=correlation_id,
            causation_id=event_id,
            payload={
                "ticket_id": str(ticket.id),
                "booking_id": str(ticket.booking_id),
                "booking_code": ticket.booking_code,
                "customer_name": ticket.customer_name,
                "customer_email": ticket.customer_email,
                "customer_phone": ticket.customer_phone,
                "court_name": ticket.court_name,
                "branch_name": ticket.branch_name,
                "location_name": ticket.location_name,
                "location_address": ticket.location_address,
                "play_date": ticket.play_date.isoformat(),
                "start_hour": ticket.start_hour,
                "end_hour": ticket.end_hour,
                "total_amount": float(ticket.total_amount),
                "qr_payload": ticket.qr_payload,
            },
        )
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.info("Concurrent ticket creation prevented by DB constraint for %s", booking_code)
            return
        logger.info("Issued ticket %s and queued ticket.issued for %s", ticket.id, booking_code)


async def revoke_ticket_by_booking(event_data: dict) -> None:
    booking_code = str(event_data["booking_code"]).strip()
    event_id = resolve_event_id(event_data, f"booking.cancelled:{booking_code}")
    correlation_id = str(event_data.get("correlation_id") or event_id)

    async with AsyncSessionLocal() as db:
        claimed = await claim_inbox_event(
            db,
            consumer_name="checkin-qr-service.booking_cancelled",
            event_id=event_id,
            event_type="booking.cancelled",
            correlation_id=correlation_id,
        )
        if not claimed:
            EVENTS_DUPLICATE_TOTAL.labels(
                service=settings.service_name, event_type="booking.cancelled"
            ).inc()
            return

        await db.execute(
            pg_insert(CancelledBooking)
            .values(booking_code=booking_code, cancelled_at=datetime.now(timezone.utc))
            .on_conflict_do_nothing(index_elements=["booking_code"])
        )
        await db.execute(
            update(CheckinTicket)
            .where(CheckinTicket.booking_code == booking_code, CheckinTicket.status == "VALID")
            .values(status="REVOKED")
        )
        await db.commit()
        logger.info("Revoked ticket (if VALID) for cancelled booking_code=%s", booking_code)


async def reschedule_ticket_from_event(event_data: dict) -> None:
    if str(event_data.get("status") or "") != "PAID":
        return
    booking_code = str(event_data["booking_code"]).strip()
    new_rev = int(event_data.get("new_revision") or 2)
    event_id = resolve_event_id(event_data, f"booking.rescheduled:{booking_code}:r{new_rev}")
    correlation_id = str(event_data.get("correlation_id") or event_id)

    async with AsyncSessionLocal() as db:
        claimed = await claim_inbox_event(
            db,
            consumer_name="checkin-qr-service.booking_rescheduled",
            event_id=event_id,
            event_type="booking.rescheduled",
            correlation_id=correlation_id,
        )
        if not claimed:
            return

        cancelled = await db.scalar(
            select(CancelledBooking).where(CancelledBooking.booking_code == booking_code)
        )
        if cancelled:
            await db.commit()
            return

        ticket = await db.scalar(
            select(CheckinTicket).where(CheckinTicket.booking_code == booking_code).with_for_update()
        )
        if ticket and ticket.booking_revision >= new_rev:
            await db.commit()
            logger.info("Skipping stale booking.rescheduled r%s for %s (current r%s)", new_rev, booking_code, ticket.booking_revision)
            return

        play_date_raw = event_data["play_date"]
        play_date = play_date_raw if isinstance(play_date_raw, date) else date.fromisoformat(str(play_date_raw))

        if ticket:
            qr_payload, qr_sig = sign_qr_payload(ticket.id, booking_code, new_rev)
            ticket.court_name = event_data["court_name"]
            ticket.branch_name = event_data.get("branch_name", ticket.branch_name)
            ticket.location_name = event_data.get("location_name", ticket.location_name)
            ticket.location_address = event_data.get("location_address", ticket.location_address)
            ticket.play_date = play_date
            ticket.start_hour = int(event_data["start_hour"])
            ticket.end_hour = int(event_data["end_hour"])
            ticket.qr_payload = qr_payload
            ticket.qr_signature = qr_sig
            ticket.booking_revision = new_rev
            if ticket.status != "CHECKED_IN":
                ticket.status = "VALID"
        else:
            ticket_id = uuid.uuid4()
            qr_payload, qr_sig = sign_qr_payload(ticket_id, booking_code, new_rev)
            ticket = CheckinTicket(
                id=ticket_id,
                booking_id=uuid.UUID(str(event_data["booking_id"])),
                booking_code=booking_code,
                customer_name=event_data["customer_name"],
                customer_email=event_data["customer_email"],
                customer_phone=event_data.get("customer_phone", ""),
                court_name=event_data["court_name"],
                branch_name=event_data.get("branch_name", ""),
                location_name=event_data.get("location_name", ""),
                location_address=event_data.get("location_address", ""),
                play_date=play_date,
                start_hour=int(event_data["start_hour"]),
                end_hour=int(event_data["end_hour"]),
                total_amount=Decimal(str(event_data.get("total_amount", 0))),
                qr_payload=qr_payload,
                qr_signature=qr_sig,
                booking_revision=new_rev,
                status="VALID",
            )
            db.add(ticket)

        enqueue_outbox_event(
            db,
            event_type="ticket.issued",
            aggregate_id=ticket.booking_code,
            correlation_id=correlation_id,
            causation_id=event_id,
            payload={
                "ticket_id": str(ticket.id),
                "booking_id": str(ticket.booking_id),
                "booking_code": ticket.booking_code,
                "customer_name": ticket.customer_name,
                "customer_email": ticket.customer_email,
                "customer_phone": ticket.customer_phone,
                "court_name": ticket.court_name,
                "branch_name": ticket.branch_name,
                "location_name": ticket.location_name,
                "location_address": ticket.location_address,
                "play_date": ticket.play_date.isoformat(),
                "start_hour": ticket.start_hour,
                "end_hour": ticket.end_hour,
                "total_amount": float(ticket.total_amount),
                "qr_payload": ticket.qr_payload,
            },
        )
        await db.commit()


async def start_consumers() -> None:
    rmq_client.set_consumer_setup(_setup_checkin_consumers)
    await _setup_checkin_consumers()


async def _setup_checkin_consumers() -> None:
    if not rmq_client.channel or not rmq_client.exchange:
        return
    queue = await rmq_client.channel.declare_queue(
        "checkin.events.v2",
        durable=True,
        arguments={"x-dead-letter-exchange": DLX_NAME},
    )
    await queue.bind(rmq_client.exchange, routing_key="booking.confirmed")
    await queue.bind(rmq_client.exchange, routing_key="booking.cancelled")
    await queue.bind(rmq_client.exchange, routing_key="booking.rescheduled")
    await queue.bind(rmq_client.exchange, routing_key="booking.no_show")
    await queue.bind(rmq_client.exchange, routing_key="booking.completed")

    async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            data = json.loads(message.body.decode("utf-8"))
            if not isinstance(data, dict) or not data.get("event") or not data.get("booking_code"):
                raise ValueError("Missing event or booking_code in checkin event")
            event_name = str(data["event"])
            if event_name == "booking.confirmed":
                for field in ("booking_id", "customer_name", "customer_email", "court_name", "play_date", "start_hour", "end_hour"):
                    if field not in data:
                        raise ValueError(f"Missing required field {field} in booking.confirmed")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            logger.error("Permanent failure parsing checkin event, routing to DLQ: %s", exc)
            EVENTS_DLQ_TOTAL.labels(service=settings.service_name, event_type="unknown").inc()
            await message.reject(requeue=False)
            return

        event_name = str(data["event"])
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                if event_name == "booking.confirmed":
                    await issue_ticket_from_booking_confirmed(data)
                elif event_name in ("booking.cancelled", "booking.no_show", "booking.completed"):
                    await revoke_ticket_by_booking(data)
                elif event_name == "booking.rescheduled":
                    await reschedule_ticket_from_event(data)
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


async def scan_and_checkin(
    db: AsyncSession,
    qr_data: str,
    staff_email: str,
    bypass_time_check: bool = False,
) -> ScanQRResponse:
    raw = qr_data.strip()

    qr_rev: int | None = None
    if raw.startswith("PKB1."):
        parts = raw.split(".")
        if len(parts) == 4:
            _, ticket_id_str, booking_code, provided_sig = parts
            qr_rev = 1
        elif len(parts) == 5 and parts[3].startswith("r") and parts[3][1:].isdigit():
            _, ticket_id_str, booking_code, rev_part, provided_sig = parts
            qr_rev = int(rev_part[1:])
        else:
            QR_SCANS_TOTAL.labels(result="invalid_signature").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định dạng mã QR không hợp lệ",
            )
        try:
            ticket_uuid = uuid.UUID(ticket_id_str)
        except ValueError as exc:
            QR_SCANS_TOTAL.labels(result="invalid_signature").inc()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã QR không hợp lệ") from exc

        _, expected_sig = sign_qr_payload(ticket_uuid, booking_code, qr_rev)
        if not hmac.compare_digest(expected_sig, provided_sig):
            QR_SCANS_TOTAL.labels(result="invalid_signature").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chữ ký HMAC mã QR không hợp lệ (nghi ngờ vé giả mạo)",
            )
        ticket = await db.scalar(select(CheckinTicket).where(CheckinTicket.id == ticket_uuid))
        if ticket and qr_rev != ticket.booking_revision:
            QR_SCANS_TOTAL.labels(result="revoked").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vé QR thuộc phiên bản lịch cũ (v{qr_rev}), không còn hiệu lực. Vui lòng dùng vé mới nhất (v{ticket.booking_revision}).",
            )
    else:
        # Manual booking_code entry fallback by Staff
        ticket = await db.scalar(select(CheckinTicket).where(CheckinTicket.booking_code == raw))

    if not ticket:
        QR_SCANS_TOTAL.labels(result="not_found").inc()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy vé đặt sân")

    if ticket.status == "REVOKED":
        QR_SCANS_TOTAL.labels(result="revoked").inc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vé đã bị hủy, không thể vào sân")

    if ticket.status == "CHECKED_IN":
        QR_SCANS_TOTAL.labels(result="already_used").inc()
        checked_str = ticket.checked_in_at.astimezone(VN_TZ).strftime("%H:%M:%S %d/%m/%Y") if ticket.checked_in_at else ""
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vé đã được quét check-in trước đó lúc {checked_str} (Chống quét lại)",
        )

    # Validate play date and time window (allow 30 minutes early check-in until end_hour)
    if not (bypass_time_check and settings.allow_demo_bypass_time):
        now_vn = datetime.now(VN_TZ)
        window_start = datetime.combine(ticket.play_date, dt_time(ticket.start_hour, 0), tzinfo=VN_TZ) - timedelta(
            minutes=30
        )
        end_hour_clamped = ticket.end_hour if ticket.end_hour < 24 else 23
        end_minute = 0 if ticket.end_hour < 24 else 59
        window_end = datetime.combine(ticket.play_date, dt_time(end_hour_clamped, end_minute), tzinfo=VN_TZ)

        if now_vn < window_start or now_vn > window_end:
            QR_SCANS_TOTAL.labels(result="wrong_time").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Chưa tới hoặc đã quá khung giờ check-in. Vé hợp lệ cho ngày {ticket.play_date.strftime('%d/%m/%Y')} "
                    f"từ {ticket.start_hour:02d}:00 - {ticket.end_hour:02d}:00 (được vào sớm 30 phút)."
                ),
            )

    # Authoritative atomic admission claim in court-booking-service (serializes check-in vs cancellation)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            claim_resp = await client.post(
                f"{settings.booking_service_url}/api/bookings/internal/{ticket.booking_code}/claim-checkin",
                headers={"X-Internal-Key": settings.internal_api_key},
                json={
                    "ticket_id": str(ticket.id),
                    "staff_email": staff_email,
                    "expected_revision": ticket.booking_revision,
                },
            )
        if claim_resp.status_code == 409:
            detail_msg = str(claim_resp.json().get("detail") or "")
            if "hủy" in detail_msg or "hết hạn" in detail_msg:
                await db.execute(
                    update(CheckinTicket)
                    .where(CheckinTicket.id == ticket.id, CheckinTicket.status == "VALID")
                    .values(status="REVOKED")
                )
                await db.commit()
                QR_SCANS_TOTAL.labels(result="revoked").inc()
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail_msg)
            QR_SCANS_TOTAL.labels(result="already_used").inc()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail_msg)
        if claim_resp.status_code >= 400:
            detail_msg = str(claim_resp.json().get("detail") or "Không thể xác nhận quyền check-in")
            QR_SCANS_TOTAL.labels(result="not_paid").inc()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail_msg)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Could not claim check-in admission for %s: %s", ticket.booking_code, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể xác minh và khóa quyền check-in với hệ thống đặt sân",
        ) from exc

    # Atomic conditional update to guarantee single-use even under concurrent scans
    now_utc = datetime.now(timezone.utc)
    result = await db.execute(
        update(CheckinTicket)
        .where(CheckinTicket.id == ticket.id, CheckinTicket.status == "VALID")
        .values(status="CHECKED_IN", checked_in_by=staff_email, checked_in_at=now_utc)
        .returning(CheckinTicket.id)
    )
    updated_id = result.scalar_one_or_none()
    await db.commit()

    if not updated_id:
        QR_SCANS_TOTAL.labels(result="already_used").inc()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vé vừa được sử dụng ở thiết bị khác",
        )

    await db.refresh(ticket)
    QR_SCANS_TOTAL.labels(result="success").inc()
    return ScanQRResponse(
        valid=True,
        code="CHECKED_IN",
        message=f"Check-in thành công! Mời khách vào {ticket.court_name} ({ticket.start_hour:02d}:00 - {ticket.end_hour:02d}:00)",
        ticket=TicketResponse.model_validate(ticket),
    )
