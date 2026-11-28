from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.metrics import AUTH_REJECTED_TOTAL
from app.models import BookingOrder
from app.schemas import (
    AdminStatsResponse,
    BookingAuthorizeRequest,
    BookingAuthorizeResponse,
    BookingResponse,
    CancelBookingRequest,
    CreateBookingRequest,
)
from app.security import (
    get_current_claims,
    get_optional_claims,
    require_roles,
    verify_guest_token,
    verify_internal_key,
)
from app.services.booking_service import (
    create_booking,
    get_admin_stats,
    release_booking_slots,
)

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


def _is_authorized_for_order(
    order: BookingOrder,
    claims: dict | None,
    guest_token: str | None,
    *,
    allow_staff: bool = True,
) -> tuple[bool, str | None]:
    role = claims.get("role") if claims else None
    if role == "ADMIN" or (allow_staff and role == "STAFF"):
        return True, None
    if order.user_id is not None:
        if claims and claims.get("sub"):
            try:
                if uuid.UUID(claims["sub"]) == order.user_id:
                    return True, None
            except ValueError:
                pass
        return False, "Bạn không có quyền truy cập đơn đặt sân này"
    # Guest booking (user_id is None)
    if order.guest_token_revoked_at is not None:
        return False, "Mã truy cập đơn khách vãng lai đã bị thu hồi"
    if order.guest_token_expires_at is not None and datetime.now(timezone.utc) > order.guest_token_expires_at:
        return False, "Mã truy cập đơn khách vãng lai đã hết hạn"
    if order.guest_token_hash and verify_guest_token(guest_token, order.guest_token_hash):
        return True, None
    if not order.guest_token_hash:
        return False, "Đơn khách vãng lai cũ cần nhân viên hoặc quản trị viên hỗ trợ tra cứu"
    return False, "Thiếu hoặc sai mã truy cập đơn khách vãng lai (X-Guest-Token)"


def _enforce_booking_access(
    order: BookingOrder,
    claims: dict | None,
    guest_token: str | None,
    *,
    endpoint_label: str,
    allow_staff: bool = True,
) -> None:
    ok, reason = _is_authorized_for_order(order, claims, guest_token, allow_staff=allow_staff)
    if ok:
        return
    AUTH_REJECTED_TOTAL.labels(service=settings.service_name, endpoint=endpoint_label).inc()
    if not claims and not guest_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=reason or "Vui lòng đăng nhập hoặc cung cấp mã truy cập đơn hàng",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=reason or "Không có quyền truy cập đơn đặt sân này",
    )


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
        .options(selectinload(BookingOrder.slots))
        .where(BookingOrder.user_id == user_id)
        .order_by(BookingOrder.created_at.desc())
    )
    return [BookingResponse.model_validate(o) for o in rows.all()]


@router.get("/admin/list", response_model=list[BookingResponse])
async def admin_list_bookings(
    _: dict = Depends(require_roles("ADMIN", "STAFF")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .order_by(BookingOrder.created_at.desc())
        .limit(100)
    )
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
    order = await db.scalar(
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .where(BookingOrder.booking_code == booking_code)
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    if order.status in ("CANCELLED", "EXPIRED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn đã ở trạng thái hủy hoặc hết hạn")
    return await release_booking_slots(db, request.app.state.redis, order, "CANCELLED", payload.reason)


@router.post("/admin/{booking_code}/revoke-guest-token")
async def admin_revoke_guest_token(
    booking_code: str,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(select(BookingOrder).where(BookingOrder.booking_code == booking_code.strip()))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    order.guest_token_revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"revoked": True, "booking_code": order.booking_code}


@router.get("/lookup/{booking_code}", response_model=BookingResponse)
async def lookup_booking(
    booking_code: str,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .where(BookingOrder.booking_code == booking_code.strip())
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mã đặt sân")
    _enforce_booking_access(order, claims, x_guest_token, endpoint_label="lookup", allow_staff=True)
    return BookingResponse.model_validate(order)


@router.get("/internal/{booking_code}", response_model=BookingResponse)
async def internal_get_booking(
    booking_code: str,
    _: None = Depends(verify_internal_key),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .where(BookingOrder.booking_code == booking_code.strip())
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return BookingResponse.model_validate(order)


@router.post("/internal/{booking_code}/authorize", response_model=BookingAuthorizeResponse)
async def internal_authorize_booking(
    booking_code: str,
    payload: BookingAuthorizeRequest,
    _: None = Depends(verify_internal_key),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(BookingOrder).where(BookingOrder.booking_code == booking_code.strip())
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    claims = {"sub": payload.user_id, "role": payload.role} if (payload.user_id or payload.role) else None
    ok, reason = _is_authorized_for_order(
        order,
        claims,
        payload.guest_token,
        allow_staff=not payload.require_owner,
    )
    return BookingAuthorizeResponse(
        authorized=ok,
        booking_code=order.booking_code,
        status=order.status,
        total_amount=float(order.total_amount),
        reason=reason,
    )


@router.post("/{booking_code}/cancel", response_model=BookingResponse)
async def customer_cancel_booking(
    booking_code: str,
    request: Request,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .where(BookingOrder.booking_code == booking_code.strip())
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    _enforce_booking_access(order, claims, x_guest_token, endpoint_label="cancel", allow_staff=False)
    if order.status != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ có thể hủy đơn khi chưa thanh toán. Đơn đã thanh toán vui lòng liên hệ Admin.",
        )
    return await release_booking_slots(
        db, request.app.state.redis, order, "CANCELLED", "Khách hàng hủy trước khi thanh toán"
    )
