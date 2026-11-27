import asyncio
import io
import json
import logging
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import make_msgid

import aio_pika
import aiosmtplib
import qrcode
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.events.rabbitmq import DLX_NAME, rmq_client
from app.metrics import EMAILS_SENT_TOTAL
from app.models import NotificationLog

logger = logging.getLogger(__name__)


def _build_qr_png_bytes(qr_payload: str) -> bytes:
    img = qrcode.make(qr_payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_ticket_email(ticket_event: dict) -> EmailMessage:
    booking_code = ticket_event["booking_code"]
    customer_name = ticket_event["customer_name"]
    recipient_email = ticket_event["customer_email"]
    court_name = ticket_event["court_name"]
    branch_name = ticket_event.get("branch_name") or "Chi nhánh 1"
    location_name = ticket_event.get("location_name") or "Cơ sở chính"
    location_address = ticket_event.get("location_address") or ""
    play_date = ticket_event["play_date"]
    start_hour = int(ticket_event["start_hour"])
    end_hour = int(ticket_event["end_hour"])
    total_amount = float(ticket_event.get("total_amount", 0))
    qr_payload = ticket_event["qr_payload"]

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = recipient_email
    msg["Subject"] = f"[Pickleball SOA] Vé QR check-in sân - Mã đơn {booking_code}"

    qr_cid = make_msgid(domain="pickleball-soa.vn")
    qr_cid_clean = qr_cid[1:-1]

    address_line_txt = f"- Địa chỉ: {location_address}\n" if location_address else ""
    address_row_html = (
        f'<tr><td style="padding: 8px 0; color: #6b7280;">Địa chỉ sân:</td>'
        f'<td style="padding: 8px 0; font-weight: bold;">{location_address}</td></tr>'
        if location_address
        else ""
    )

    plain_text = (
        f"Xin chào {customer_name},\n\n"
        f"Thanh toán đặt sân Pickleball của bạn đã được xác nhận!\n"
        f"- Mã đặt sân: {booking_code}\n"
        f"- Chi nhánh: {branch_name}\n"
        f"- Địa điểm: {location_name}\n"
        f"{address_line_txt}"
        f"- Sân: {court_name}\n"
        f"- Ngày chơi: {play_date}\n"
        f"- Khung giờ: {start_hour:02d}:00 - {end_hour:02d}:00\n"
        f"- Tổng tiền: {total_amount:,.0f} VNĐ\n\n"
        f"Vui lòng xuất trình mã QR đính kèm cho nhân viên tại quầy để check-in vào sân (hỗ trợ vào sớm 30 phút).\n"
    )
    msg.set_content(plain_text)

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #f3f7f4; padding: 24px; color: #1f2937;">
        <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #d1fae5;">
          <div style="background: #065f46; color: #ffffff; padding: 20px 24px;">
            <h2 style="margin: 0; font-size: 20px;">XÁC NHẬN ĐẶT SÂN PICKLEBALL</h2>
            <p style="margin: 6px 0 0 0; font-size: 13px; color: #a7f3d0;">{branch_name} • {location_name}</p>
          </div>
          <div style="padding: 24px;">
            <p>Xin chào <strong>{customer_name}</strong>,</p>
            <p>Đơn đặt sân của bạn đã được thanh toán thành công. Dưới đây là thông tin vé điện tử và mã QR check-in tại sân:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;">
              <tr><td style="padding: 8px 0; color: #6b7280; width: 36%;">Mã đơn:</td><td style="padding: 8px 0; font-weight: bold;">{booking_code}</td></tr>
              <tr><td style="padding: 8px 0; color: #6b7280;">Chi nhánh:</td><td style="padding: 8px 0; font-weight: bold; color: #065f46;">{branch_name}</td></tr>
              <tr><td style="padding: 8px 0; color: #6b7280;">Địa điểm:</td><td style="padding: 8px 0; font-weight: bold;">{location_name}</td></tr>
              {address_row_html}
              <tr><td style="padding: 8px 0; color: #6b7280;">Sân thi đấu:</td><td style="padding: 8px 0; font-weight: bold;">{court_name}</td></tr>
              <tr><td style="padding: 8px 0; color: #6b7280;">Ngày chơi:</td><td style="padding: 8px 0; font-weight: bold;">{play_date}</td></tr>
              <tr><td style="padding: 8px 0; color: #6b7280;">Khung giờ:</td><td style="padding: 8px 0; font-weight: bold;">{start_hour:02d}:00 - {end_hour:02d}:00</td></tr>
              <tr><td style="padding: 8px 0; color: #6b7280;">Tổng thanh toán:</td><td style="padding: 8px 0; font-weight: bold; color: #059669;">{total_amount:,.0f} VNĐ</td></tr>
            </table>
            <div style="text-align: center; background: #f9fafb; padding: 20px; border-radius: 10px; border: 1px dashed #10b981;">
              <p style="margin: 0 0 12px 0; font-weight: bold; color: #065f46;">MÃ QR CHECK-IN VÀO SÂN</p>
              <img src="cid:{qr_cid_clean}" alt="QR Check-in" style="width: 220px; height: 220px;" />
              <p style="margin: 10px 0 0 0; font-size: 11px; color: #6b7280; word-break: break-all;">{qr_payload}</p>
            </div>
            <p style="font-size: 12px; color: #6b7280; margin-top: 16px;">
              Lưu ý: Mã QR chỉ có giá trị sử dụng 01 lần duy nhất và cho phép check-in sớm tối đa 30 phút trước giờ chơi.
            </p>
          </div>
        </div>
      </body>
    </html>
    """
    msg.add_alternative(html_body, subtype="html")

    qr_bytes = _build_qr_png_bytes(qr_payload)
    html_part = msg.get_payload()[1]
    html_part.add_related(qr_bytes, maintype="image", subtype="png", cid=qr_cid, filename=f"qr-{booking_code}.png")
    msg.add_attachment(qr_bytes, maintype="image", subtype="png", filename=f"ticket-{booking_code}.png")
    return msg


async def send_email_with_retry(ticket_event: dict) -> None:
    booking_code = ticket_event["booking_code"]
    recipient_email = ticket_event["customer_email"]

    async with AsyncSessionLocal() as db:
        already_sent = await db.scalar(
            select(NotificationLog).where(
                NotificationLog.booking_code == booking_code,
                NotificationLog.status == "SENT",
            )
        )
        if already_sent:
            return

    msg = _build_ticket_email(ticket_event)
    max_retries = 3
    last_error: str | None = None

    for attempt in range(1, max_retries + 1):
        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                start_tls=settings.smtp_use_tls,
                timeout=10,
            )
            async with AsyncSessionLocal() as db:
                db.add(
                    NotificationLog(
                        booking_code=booking_code,
                        recipient_email=recipient_email,
                        subject=msg["Subject"],
                        channel="EMAIL",
                        status="SENT",
                        retry_count=attempt - 1,
                        sent_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()
            EMAILS_SENT_TOTAL.labels(status="sent").inc()
            logger.info("Sent QR email for %s to %s", booking_code, recipient_email)
            return
        except Exception as exc:
            last_error = str(exc)
            logger.warning("SMTP attempt %s/%s failed for %s: %s", attempt, max_retries, booking_code, exc)
            if attempt < max_retries:
                await asyncio.sleep(1.5 * attempt)

    async with AsyncSessionLocal() as db:
        db.add(
            NotificationLog(
                booking_code=booking_code,
                recipient_email=recipient_email,
                subject=msg["Subject"],
                channel="EMAIL",
                status="FAILED",
                retry_count=max_retries,
                error_message=last_error,
            )
        )
        await db.commit()
    EMAILS_SENT_TOTAL.labels(status="failed").inc()
    raise RuntimeError(f"Failed sending email after {max_retries} attempts: {last_error}")


async def start_ticket_consumer() -> None:
    if not rmq_client.channel or not rmq_client.exchange:
        return
    queue = await rmq_client.channel.declare_queue(
        "notification.ticket_email",
        durable=True,
        arguments={"x-dead-letter-exchange": DLX_NAME},
    )
    await queue.bind(rmq_client.exchange, routing_key="ticket.issued")

    async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            data = json.loads(message.body.decode("utf-8"))
            await send_email_with_retry(data)
            await message.ack()
        except Exception as exc:
            logger.error("Routing message to DLQ due to error: %s", exc)
            await message.reject(requeue=False)

    await queue.consume(_on_message)
