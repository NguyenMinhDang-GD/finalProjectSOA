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
import qrcode
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.events.rabbitmq import rmq_client
from app.metrics import QR_SCANS_TOTAL
from app.models import CheckinTicket
from app.schemas import ScanQRResponse, TicketResponse

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def sign_qr_payload(ticket_id: uuid.UUID, booking_code: str) -> tuple[str, str]:
    msg = f"{ticket_id}:{booking_code}"
    sig = hmac.new(
        settings.qr_hmac_secret.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]
    payload = f"PKB1.{ticket_id}.{booking_code}.{sig}"
    return payload, sig


def generate_qr_base64(qr_payload: str) -> str:
    img = qrcode.make(qr_payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


async def issue_ticket_from_payment(event_data: dict) -> None:
    booking_code = event_data["booking_code"]
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(CheckinTicket).where(CheckinTicket.booking_code == booking_code))
        if existing:
            return

        ticket_id = uuid.uuid4()
        qr_payload, qr_sig = sign_qr_payload(ticket_id, booking_code)

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
            status="VALID",
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)

    await rmq_client.publish(
        "ticket.issued",
        {
            "event": "ticket.issued",
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


async def revoke_ticket_by_booking(booking_code: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(CheckinTicket)
            .where(CheckinTicket.booking_code == booking_code, CheckinTicket.status == "VALID")
            .values(status="REVOKED")
        )
        await db.commit()


async def start_consumers() -> None:
    if not rmq_client.channel or not rmq_client.exchange:
        return
    queue = await rmq_client.channel.declare_queue("checkin.events", durable=True)
    await queue.bind(rmq_client.exchange, routing_key="payment.succeeded")
    await queue.bind(rmq_client.exchange, routing_key="booking.cancelled")

    async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            data = json.loads(message.body.decode("utf-8"))
            event_name = data.get("event")
            if event_name == "payment.succeeded":
                await issue_ticket_from_payment(data)
            elif event_name == "booking.cancelled" and data.get("booking_code"):
                await revoke_ticket_by_booking(data["booking_code"])

    await queue.consume(_on_message)


async def scan_and_checkin(
    db: AsyncSession,
    qr_data: str,
    staff_email: str,
    bypass_time_check: bool = False,
) -> ScanQRResponse:
    raw = qr_data.strip()

    if raw.startswith("PKB1."):
        parts = raw.split(".")
        if len(parts) != 4:
            QR_SCANS_TOTAL.labels(result="invalid_signature").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định dạng mã QR không hợp lệ",
            )
        _, ticket_id_str, booking_code, provided_sig = parts
        try:
            ticket_uuid = uuid.UUID(ticket_id_str)
        except ValueError as exc:
            QR_SCANS_TOTAL.labels(result="invalid_signature").inc()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã QR không hợp lệ") from exc

        _, expected_sig = sign_qr_payload(ticket_uuid, booking_code)
        if not hmac.compare_digest(expected_sig, provided_sig):
            QR_SCANS_TOTAL.labels(result="invalid_signature").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chữ ký HMAC mã QR không hợp lệ (nghi ngờ vé giả mạo)",
            )
        ticket = await db.scalar(select(CheckinTicket).where(CheckinTicket.id == ticket_uuid))
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
