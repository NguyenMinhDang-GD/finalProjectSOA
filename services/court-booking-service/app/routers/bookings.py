import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import BookingOrder
from app.schemas import (
    AdminStatsResponse,
    BookingResponse,
    CancelBookingRequest,
    CreateBookingRequest,
)
from app.security import (
    get_current_claims,
    get_optional_claims,
    require_roles,
    verify_internal_key,
)
from app.services.booking_service import (
    create_booking,
    get_admin_stats,
    release_booking_slots,
)

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking_endpoint(
    payload: CreateBookingRequest,
    request: Request,
    claims: dict | None = Depends(get_optional_claims),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(claims["sub"]) if claims else None
    return await create_booking(db, request.app.state.redis, payload, user_id)


@router.get("/my", response_model=list[BookingResponse])
async def my_bookings(
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(claims["sub"])
    rows = await db.scalars(
        select(BookingOrder)
        .where(BookingOrder.user_id == user_id)
        .order_by(BookingOrder.created_at.desc())
    )
    return [BookingResponse.model_validate(o) for o in rows.all()]


@router.get("/admin/list", response_model=list[BookingResponse])
async def admin_list_bookings(
    _: dict = Depends(require_roles("ADMIN", "STAFF")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(select(BookingOrder).order_by(BookingOrder.created_at.desc()).limit(100))
    return [BookingResponse.model_validate(o) for o in rows.all()]


@router.get("/admin/stats", response_model=AdminStatsResponse)
async def admin_stats(
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await get_admin_stats(db)


@router.post("/admin/{booking_code}/cancel", response_model=BookingResponse)
async def admin_cancel_booking(
    booking_code: str,
    payload: CancelBookingRequest,
    request: Request,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(select(BookingOrder).where(BookingOrder.booking_code == booking_code))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    if order.status in ("CANCELLED", "EXPIRED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn đã ở trạng thái hủy hoặc hết hạn")
    return await release_booking_slots(db, request.app.state.redis, order, "CANCELLED", payload.reason)


@router.get("/lookup/{booking_code}", response_model=BookingResponse)
async def lookup_booking(booking_code: str, db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(BookingOrder).where(BookingOrder.booking_code == booking_code.strip()))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mã đặt sân")
    return BookingResponse.model_validate(order)


@router.get("/internal/{booking_code}", response_model=BookingResponse)
async def internal_get_booking(
    booking_code: str,
    _: None = Depends(verify_internal_key),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(select(BookingOrder).where(BookingOrder.booking_code == booking_code.strip()))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return BookingResponse.model_validate(order)


@router.post("/{booking_code}/cancel", response_model=BookingResponse)
async def customer_cancel_booking(
    booking_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(select(BookingOrder).where(BookingOrder.booking_code == booking_code.strip()))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    if order.status != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ có thể hủy đơn khi chưa thanh toán. Đơn đã thanh toán vui lòng liên hệ Admin.",
        )
    return await release_booking_slots(
        db, request.app.state.redis, order, "CANCELLED", "Khách hàng hủy trước khi thanh toán"
    )
