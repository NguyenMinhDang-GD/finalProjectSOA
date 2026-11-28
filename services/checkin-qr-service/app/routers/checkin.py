from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import CheckinTicket
from app.schemas import ScanQRRequest, ScanQRResponse, TicketResponse
from app.security import authorize_booking_access, get_optional_claims, require_roles, verify_internal_key
from app.services.checkin_service import generate_qr_base64, scan_and_checkin

router = APIRouter(prefix="/api/checkin", tags=["QR Tickets & Check-in"])


@router.get("/internal/ticket/{booking_code}")
async def internal_get_ticket_status(
    booking_code: str,
    _: None = Depends(verify_internal_key),
    db: AsyncSession = Depends(get_db),
):
    ticket = await db.scalar(select(CheckinTicket).where(CheckinTicket.booking_code == booking_code.strip()))
    if not ticket:
        return {"exists": False, "booking_code": booking_code.strip(), "status": None}
    return {
        "exists": True,
        "booking_code": ticket.booking_code,
        "status": ticket.status,
        "checked_in_at": ticket.checked_in_at.isoformat() if ticket.checked_in_at else None,
    }


@router.get("/ticket/{booking_code}", response_model=TicketResponse)
async def get_ticket_by_booking(
    booking_code: str,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    await authorize_booking_access(booking_code, claims, x_guest_token)
    ticket = await db.scalar(select(CheckinTicket).where(CheckinTicket.booking_code == booking_code.strip()))
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vé QR chưa được phát hành hoặc không tồn tại")
    res = TicketResponse.model_validate(ticket)
    res.qr_image_base64 = generate_qr_base64(ticket.qr_payload)
    return res


@router.post("/scan", response_model=ScanQRResponse)
async def scan_qr(
    payload: ScanQRRequest,
    claims: dict = Depends(require_roles("STAFF", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    if payload.bypass_time_check and not settings.is_demo_bypass_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chế độ bỏ qua kiểm tra khung giờ đang tắt",
        )
    return await scan_and_checkin(
        db=db,
        qr_data=payload.qr_data,
        staff_email=claims.get("email", "staff"),
        bypass_time_check=payload.bypass_time_check,
    )


@router.get("/logs", response_model=list[TicketResponse])
async def list_checkin_logs(
    _: dict = Depends(require_roles("STAFF", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(select(CheckinTicket).order_by(CheckinTicket.created_at.desc()).limit(100))
    return [TicketResponse.model_validate(t) for t in rows.all()]
