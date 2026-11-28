from datetime import date, datetime, timezone
import uuid
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.metrics import AUTH_REJECTED_TOTAL
from app.models import (
    BookingOrder,
    BookingRescheduleHistory,
    MaintenanceBlock,
    OperationalAuditLog,
)
from app.schemas import (
    AdminStatsResponse,
    BookingAuthorizeRequest,
    BookingAuthorizeResponse,
    BookingResponse,
    CancelBookingRequest,
    CancellationQuoteResponse,
    ClaimCheckinRequest,
    ClaimCheckinResponse,
    CompleteBookingRequest,
    CreateBookingRequest,
    CreateMaintenanceRequest,
    MaintenanceBlockResponse,
    NoShowRequest,
    OperationalAuditLogResponse,
    RescheduleBookingRequest,
    RescheduleHistoryResponse,
    RescheduleQuoteRequest,
    RescheduleQuoteResponse,
    WalkInBookingRequest,
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
    evaluate_cancellation_policy,
    get_admin_stats,
    release_booking_slots,
    trigger_internal_refund,
)
from app.services.operations_service import (
    cancel_maintenance_block,
    complete_booking,
    create_maintenance_block,
    evaluate_reschedule_quote,
    mark_booking_no_show,
    record_operational_audit,
    reschedule_booking,
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
    claims: dict = Depends(require_roles("ADMIN")),
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

    quote = await evaluate_cancellation_policy(order)
    if quote["is_checked_in"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vé đã check-in vào sân, không thể hủy đơn",
        )

    refund_snapshot = None
    if order.status == "PAID":
        if payload.admin_exception:
            if not payload.reason or len(payload.reason.strip()) < 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Hủy ngoại lệ Admin bắt buộc phải nhập lý do",
                )
            pct = payload.override_refund_percent if payload.override_refund_percent is not None else 100
            refund_amt = int(round(quote["total_amount"] * pct / 100))
            tier = "ADMIN_EXCEPTION"
            override_reason = payload.reason.strip()
        else:
            pct = quote["refund_percent"]
            refund_amt = quote["estimated_refund_amount"]
            tier = quote["policy_tier"]
            override_reason = None

        refund_snapshot = {
            "policy_tier": tier,
            "policy_percent": pct,
            "refund_amount_vnd": refund_amt,
            "admin_override_reason": override_reason,
            "cancelled_by": str(claims.get("email") or "admin"),
        }
        result = await release_booking_slots(
            db, request.app.state.redis, order, "CANCELLED", payload.reason, refund_snapshot=refund_snapshot
        )
        if refund_amt > 0:
            await trigger_internal_refund(
                booking_code=result.booking_code,
                requested_amount=refund_amt,
                policy_tier=tier,
                policy_percent=pct,
                reason=payload.reason,
                admin_override_reason=override_reason,
            )
        return result

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


@router.post("/internal/{booking_code}/claim-checkin", response_model=ClaimCheckinResponse)
async def internal_claim_checkin(
    booking_code: str,
    payload: ClaimCheckinRequest,
    _: None = Depends(verify_internal_key),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(BookingOrder)
        .where(BookingOrder.booking_code == booking_code.strip())
        .with_for_update()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    if order.status in ("CANCELLED", "EXPIRED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Đơn đặt sân đã bị hủy hoặc hết hạn, vé không còn hiệu lực check-in",
        )
    if order.status != "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đơn đặt sân đang ở trạng thái {order.status}, không thể check-in",
        )
    if payload.expected_revision is not None and order.booking_revision != payload.expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vé QR thuộc phiên bản lịch cũ (v{payload.expected_revision}), phiên bản hiện tại là v{order.booking_revision}",
        )
    if order.admission_status == "ADMITTED":
        if order.admission_ticket_id == payload.ticket_id:
            return ClaimCheckinResponse(
                admitted=True,
                already_admitted_same_ticket=True,
                booking_code=order.booking_code,
                status=order.status,
                admission_status=order.admission_status,
                message="Vé đã được ghi nhận vào sân (idempotent recovery)",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Đơn đặt sân đã được check-in trước đó",
        )

    order.admission_status = "ADMITTED"
    order.admission_ticket_id = payload.ticket_id
    order.checked_in_at = datetime.now(timezone.utc)
    order.checked_in_by = payload.staff_email
    record_operational_audit(
        db,
        entity_type="BOOKING",
        entity_id=order.booking_code,
        action="BOOKING_ADMITTED",
        actor=payload.staff_email,
        actor_role="STAFF",
        previous_state="NONE",
        new_state="ADMITTED",
        reason="Check-in QR hợp lệ tại sân",
        metadata={"ticket_id": payload.ticket_id, "booking_revision": order.booking_revision},
    )
    await db.commit()
    return ClaimCheckinResponse(
        admitted=True,
        already_admitted_same_ticket=False,
        booking_code=order.booking_code,
        status=order.status,
        admission_status=order.admission_status,
        message="Đã cấp quyền check-in hợp lệ",
    )


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


@router.get("/{booking_code}/cancellation-quote", response_model=CancellationQuoteResponse)
async def get_cancellation_quote(
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    _enforce_booking_access(order, claims, x_guest_token, endpoint_label="cancellation_quote", allow_staff=True)
    return CancellationQuoteResponse(**(await evaluate_cancellation_policy(order)))


@router.post("/{booking_code}/cancel", response_model=BookingResponse)
async def customer_cancel_booking(
    booking_code: str,
    request: Request,
    payload: CancelBookingRequest | None = Body(default=None),
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
    if order.status in ("CANCELLED", "EXPIRED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn đã ở trạng thái hủy hoặc hết hạn")

    cancel_reason = (payload.reason.strip() if payload and payload.reason else "") or "Khách hàng hủy đặt sân"
    if order.status == "PENDING_PAYMENT":
        return await release_booking_slots(
            db, request.app.state.redis, order, "CANCELLED", cancel_reason
        )

    quote = await evaluate_cancellation_policy(order)
    if quote["is_checked_in"] or not quote["eligible"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=quote["message"],
        )

    actor = str((claims or {}).get("email") or "customer")
    refund_amt = quote["estimated_refund_amount"]
    refund_snapshot = {
        "policy_tier": quote["policy_tier"],
        "policy_percent": quote["refund_percent"],
        "refund_amount_vnd": refund_amt,
        "cancelled_by": actor,
    }
    result = await release_booking_slots(
        db,
        request.app.state.redis,
        order,
        "CANCELLED",
        cancel_reason,
        refund_snapshot=refund_snapshot,
    )
    if refund_amt > 0:
        await trigger_internal_refund(
            booking_code=result.booking_code,
            requested_amount=refund_amt,
            policy_tier=quote["policy_tier"],
            policy_percent=quote["refund_percent"],
            reason=cancel_reason,
        )
    return result


# ----------------- B03: RESCHEDULING, WALK-IN, MAINTENANCE, NO-SHOW, COMPLETION & AUDIT -----------------


@router.post("/{booking_code}/reschedule-quote", response_model=RescheduleQuoteResponse)
async def get_reschedule_quote_endpoint(
    booking_code: str,
    payload: RescheduleQuoteRequest,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(BookingOrder).options(selectinload(BookingOrder.slots)).where(BookingOrder.booking_code == booking_code.strip())
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt sân")
    _enforce_booking_access(order, claims, x_guest_token, endpoint_label="reschedule_quote", allow_staff=True)
    is_priv = bool(claims and claims.get("role") in ("STAFF", "ADMIN"))
    return await evaluate_reschedule_quote(db, order, payload, is_privileged=is_priv)


@router.post("/{booking_code}/reschedule", response_model=BookingResponse)
async def reschedule_booking_endpoint(
    booking_code: str,
    payload: RescheduleBookingRequest,
    request: Request,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(BookingOrder).options(selectinload(BookingOrder.slots)).where(BookingOrder.booking_code == booking_code.strip())
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt sân")
    _enforce_booking_access(order, claims, x_guest_token, endpoint_label="reschedule", allow_staff=True)
    actor = str((claims or {}).get("email") or "guest")
    actor_role = str((claims or {}).get("role") or "GUEST")
    return await reschedule_booking(
        db,
        request.app.state.redis,
        booking_code,
        payload,
        actor=actor,
        actor_role=actor_role,
    )


@router.get("/{booking_code}/reschedule-history", response_model=list[RescheduleHistoryResponse])
async def get_reschedule_history_endpoint(
    booking_code: str,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(select(BookingOrder).where(BookingOrder.booking_code == booking_code.strip()))
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt sân")
    _enforce_booking_access(order, claims, x_guest_token, endpoint_label="reschedule_history", allow_staff=True)
    rows = (
        await db.scalars(
            select(BookingRescheduleHistory)
            .where(BookingRescheduleHistory.booking_code == booking_code.strip())
            .order_by(desc(BookingRescheduleHistory.created_at))
        )
    ).all()
    return [RescheduleHistoryResponse.model_validate(r) for r in rows]


@router.post("/staff/walk-in", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def staff_walk_in_booking(
    payload: WalkInBookingRequest,
    request: Request,
    claims: dict = Depends(require_roles("STAFF", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    fallback_email = payload.customer_email or f"walkin-{payload.customer_phone.strip()}@pickleball-walkin.vn"
    create_payload = CreateBookingRequest(
        court_id=payload.court_id,
        play_date=payload.play_date,
        hours=payload.hours,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=fallback_email,
    )
    return await create_booking(
        db,
        request.app.state.redis,
        create_payload,
        user_id=None,
        booking_source="WALK_IN",
        operator_email=str(claims.get("email") or "staff"),
        operator_role=str(claims.get("role") or "STAFF"),
    )


@router.post("/staff/{booking_code}/no-show", response_model=BookingResponse)
async def staff_mark_no_show(
    booking_code: str,
    payload: NoShowRequest,
    claims: dict = Depends(require_roles("STAFF", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await mark_booking_no_show(
        db,
        booking_code,
        payload,
        actor_email=str(claims.get("email") or "staff"),
        actor_role=str(claims.get("role") or "STAFF"),
    )


@router.post("/staff/{booking_code}/complete", response_model=BookingResponse)
async def staff_complete_booking(
    booking_code: str,
    payload: CompleteBookingRequest,
    claims: dict = Depends(require_roles("STAFF", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await complete_booking(
        db,
        booking_code,
        payload,
        actor_email=str(claims.get("email") or "staff"),
        actor_role=str(claims.get("role") or "STAFF"),
    )


@router.get("/maintenance", response_model=list[MaintenanceBlockResponse])
async def list_maintenance_blocks(
    play_date: date | None = Query(default=None),
    _: dict = Depends(require_roles("STAFF", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MaintenanceBlock).order_by(desc(MaintenanceBlock.play_date), MaintenanceBlock.start_hour).limit(200)
    if play_date:
        stmt = stmt.where(MaintenanceBlock.play_date == play_date)
    rows = (await db.scalars(stmt)).all()
    return [MaintenanceBlockResponse.model_validate(r) for r in rows]


@router.post("/admin/maintenance", response_model=MaintenanceBlockResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_maintenance(
    payload: CreateMaintenanceRequest,
    request: Request,
    claims: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await create_maintenance_block(
        db,
        request.app.state.redis,
        payload,
        actor_email=str(claims.get("email") or "admin"),
        actor_role=str(claims.get("role") or "ADMIN"),
    )


@router.post("/admin/maintenance/{block_id}/cancel", response_model=MaintenanceBlockResponse)
async def admin_cancel_maintenance(
    block_id: uuid.UUID,
    claims: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await cancel_maintenance_block(
        db,
        block_id,
        actor_email=str(claims.get("email") or "admin"),
        actor_role=str(claims.get("role") or "ADMIN"),
    )


@router.get("/admin/operational-audit", response_model=list[OperationalAuditLogResponse])
async def admin_list_operational_audit(
    entity_id: str | None = Query(default=None),
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(OperationalAuditLog).order_by(desc(OperationalAuditLog.created_at)).limit(300)
    if entity_id:
        stmt = stmt.where(OperationalAuditLog.entity_id == entity_id.strip())
    rows = (await db.scalars(stmt)).all()
    return [OperationalAuditLogResponse.model_validate(r) for r in rows]
