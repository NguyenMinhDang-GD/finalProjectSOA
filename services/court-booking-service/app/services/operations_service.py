"""B03 Business Operations: Rescheduling, Maintenance Scheduling, No-Show, Completion & Audit."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.events.outbox import enqueue_outbox_event
from app.metrics import (
    BOOKING_CONFLICTS_TOTAL,
    BOOKINGS_LIFECYCLE_TOTAL,
    BOOKINGS_RESCHEDULED_TOTAL,
    MAINTENANCE_BLOCKS_TOTAL,
    REDIS_LOCK_FAILURES_TOTAL,
)
from app.models import (
    BookingOrder,
    BookingRescheduleHistory,
    BookingSlot,
    Court,
    Location,
    MaintenanceBlock,
    OperationalAuditLog,
    PricingRule,
)
from app.schemas import (
    BookingResponse,
    CompleteBookingRequest,
    CreateMaintenanceRequest,
    MaintenanceBlockResponse,
    NoShowRequest,
    OperationalAuditLogResponse,
    RescheduleBookingRequest,
    RescheduleHistoryResponse,
    RescheduleQuoteRequest,
    RescheduleQuoteResponse,
)
from app.services.booking_service import (
    _find_slot_price,
    _reload_booking,
    _slot_lock_key,
    release_owned_locks,
    serialize_court,
)

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def record_operational_audit(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    actor_role: str,
    previous_state: str | None = None,
    new_state: str | None = None,
    reason: str | None = None,
    correlation_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        OperationalAuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            actor_role=actor_role,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
            correlation_id=correlation_id,
            metadata_json=metadata or {},
        )
    )


async def _check_payment_reschedule_blocked(booking_code: str) -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.payment_service_url}/api/payments/internal/{booking_code}/reschedule-check",
                headers={"X-Internal-Key": settings.internal_api_key},
            )
        if resp.status_code == 200:
            data = resp.json()
            return bool(data.get("blocked")), data.get("reason")
    except Exception as exc:
        logger.warning("Could not verify payment reschedule eligibility for %s: %s", booking_code, exc)
    return False, None


async def _sync_payment_revision(booking_code: str, new_amount: int, new_revision: int) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.payment_service_url}/api/payments/internal/{booking_code}/sync-revision",
                headers={"X-Internal-Key": settings.internal_api_key},
                json={"expected_amount": new_amount, "booking_revision": new_revision},
            )
    except Exception as exc:
        logger.warning("Sync payment revision failed for %s: %s", booking_code, exc)


async def evaluate_reschedule_quote(
    db: AsyncSession,
    order: BookingOrder,
    payload: RescheduleQuoteRequest,
    *,
    is_privileged: bool = False,
) -> RescheduleQuoteResponse:
    now_vn = datetime.now(VN_TZ)
    cur_start_vn = datetime.combine(order.play_date, dt_time(order.start_hour, 0), tzinfo=VN_TZ)
    hours_until = round((cur_start_vn - now_vn).total_seconds() / 3600.0, 2)

    court = await db.scalar(
        select(Court).where(Court.id == payload.court_id, Court.is_deleted.is_(False))
    )
    if not court or court.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Sân mới không tồn tại hoặc đang bảo trì")

    rules = (await db.scalars(select(PricingRule))).all()
    is_weekend = payload.play_date.weekday() >= 5
    new_amount = Decimal("0")
    for h in payload.hours:
        p, _ = _find_slot_price(rules, court.court_type, is_weekend, h)
        new_amount += p

    current_amount = float(order.total_amount)
    new_amount_f = float(new_amount)
    same_price = int(round(current_amount)) == int(round(new_amount_f))

    eligible = True
    reason = None
    if order.status not in ("PENDING_PAYMENT", "PAID"):
        eligible = False
        reason = f"Đơn đang ở trạng thái {order.status}, không thể đổi lịch"
    elif order.admission_status != "NONE":
        eligible = False
        reason = "Đơn đã check-in vào sân, không thể đổi lịch"
    elif not is_privileged and hours_until < settings.reschedule_cutoff_hours:
        eligible = False
        reason = f"Khách hàng cần đổi lịch trước giờ chơi ít nhất {settings.reschedule_cutoff_hours} giờ"
    elif order.status == "PAID" and not same_price:
        eligible = False
        reason = (
            "Đơn đã thanh toán chỉ hỗ trợ đổi sang khung giờ cùng mức giá. "
            "Với khung giờ khác giá, vui lòng hủy đơn theo chính sách và đặt lại."
        )
    else:
        blocked, block_reason = await _check_payment_reschedule_blocked(order.booking_code)
        if blocked:
            eligible = False
            reason = block_reason or "Đơn đang có hồ sơ đối soát hoặc hoàn tiền chưa đóng"

    return RescheduleQuoteResponse(
        booking_code=order.booking_code,
        eligible=eligible,
        reason=reason,
        current_amount=current_amount,
        new_amount=new_amount_f,
        same_price=same_price,
        hours_until_current_start=hours_until,
    )


async def reschedule_booking(
    db: AsyncSession,
    redis_client: Redis,
    booking_code: str,
    payload: RescheduleBookingRequest,
    *,
    actor: str,
    actor_role: str,
) -> BookingResponse:
    code = booking_code.strip()
    is_privileged = actor_role in ("STAFF", "ADMIN")

    # Idempotency check
    if payload.idempotency_key:
        existing_hist = await db.scalar(
            select(BookingRescheduleHistory).where(
                BookingRescheduleHistory.booking_code == code,
                BookingRescheduleHistory.idempotency_key == payload.idempotency_key,
            )
        )
        if existing_hist:
            current_order = await db.scalar(
                select(BookingOrder).options(selectinload(BookingOrder.slots)).where(BookingOrder.booking_code == code)
            )
            assert current_order is not None
            return BookingResponse.model_validate(current_order)

    # Lock BookingOrder row first, then lock old+new Court rows in deterministic sorted order
    order = await db.scalar(
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .where(BookingOrder.booking_code == code)
        .with_for_update()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt sân")

    if payload.expected_revision is not None and order.booking_revision != payload.expected_revision:
        raise HTTPException(
            status_code=409,
            detail=f"Phiên bản đơn đặt sân đã thay đổi (hiện tại: v{order.booking_revision})",
        )

    if order.status not in ("PENDING_PAYMENT", "PAID"):
        raise HTTPException(status_code=400, detail=f"Đơn đang ở trạng thái {order.status}, không thể đổi lịch")
    if order.admission_status != "NONE":
        raise HTTPException(status_code=409, detail="Đơn đã check-in vào sân, không thể đổi lịch")

    now_vn = datetime.now(VN_TZ)
    cur_start_vn = datetime.combine(order.play_date, dt_time(order.start_hour, 0), tzinfo=VN_TZ)
    hours_until = (cur_start_vn - now_vn).total_seconds() / 3600.0
    if hours_until < settings.reschedule_cutoff_hours:
        if not (is_privileged and payload.staff_override and (payload.reason or "").strip()):
            raise HTTPException(
                status_code=400,
                detail=f"Chỉ có thể đổi lịch trước giờ chơi ít nhất {settings.reschedule_cutoff_hours} giờ",
            )

    new_start_vn = datetime.combine(payload.play_date, dt_time(payload.hours[0], 0), tzinfo=VN_TZ)
    if payload.play_date < now_vn.date() or new_start_vn <= now_vn:
        raise HTTPException(status_code=400, detail="Không thể đổi sang khung giờ trong quá khứ")

    blocked, block_reason = await _check_payment_reschedule_blocked(order.booking_code)
    if blocked:
        raise HTTPException(
            status_code=409,
            detail=block_reason or "Đơn đang có sai lệch đối soát hoặc hoàn tiền chưa xử lý xong",
        )

    court_ids = sorted({order.court_id, payload.court_id}, key=lambda x: str(x))
    locked_courts = (
        await db.scalars(
            select(Court)
            .options(selectinload(Court.location).selectinload(Location.branch))
            .where(Court.id.in_(court_ids))
            .order_by(Court.id)
            .with_for_update()
        )
    ).all()
    court_map = {c.id: c for c in locked_courts}
    new_court = court_map.get(payload.court_id)
    if not new_court or new_court.is_deleted or new_court.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Sân mới không khả dụng hoặc đang bảo trì")

    rules = (await db.scalars(select(PricingRule))).all()
    is_weekend = payload.play_date.weekday() >= 5
    new_amount = Decimal("0")
    new_slot_prices: dict[int, tuple[Decimal, bool]] = {}
    for h in payload.hours:
        p, pk = _find_slot_price(rules, new_court.court_type, is_weekend, h)
        new_amount += p
        new_slot_prices[h] = (p, pk)

    if order.status == "PAID" and int(round(float(new_amount))) != int(round(float(order.total_amount))):
        BOOKINGS_RESCHEDULED_TOTAL.labels(outcome="price_mismatch").inc()
        raise HTTPException(
            status_code=400,
            detail="Đơn đã thanh toán chỉ hỗ trợ đổi sang khung giờ cùng mức giá. Với khung giờ khác giá, vui lòng hủy đơn theo chính sách và đặt lại.",
        )

    # Check maintenance overlap on new court/date/hours
    maint_overlap = await db.scalar(
        select(MaintenanceBlock).where(
            MaintenanceBlock.court_id == payload.court_id,
            MaintenanceBlock.play_date == payload.play_date,
            MaintenanceBlock.status == "SCHEDULED",
            MaintenanceBlock.start_hour < payload.hours[-1] + 1,
            MaintenanceBlock.end_hour > payload.hours[0],
        )
    )
    if maint_overlap:
        BOOKINGS_RESCHEDULED_TOTAL.labels(outcome="maintenance_conflict").inc()
        raise HTTPException(
            status_code=409,
            detail=f"Khung giờ mới trùng lịch bảo trì sân ({maint_overlap.start_hour:02d}:00 - {maint_overlap.end_hour:02d}:00)",
        )

    old_slots_set = {(s.court_id, s.play_date, s.start_hour) for s in order.slots if s.slot_status in ("LOCKED", "BOOKED")}
    new_slots_set = {(payload.court_id, payload.play_date, h) for h in payload.hours}
    if old_slots_set == new_slots_set:
        raise HTTPException(
            status_code=400,
            detail="Khung giờ mới trùng với lịch hiện tại của đơn đặt sân",
        )
    added_slots = sorted(new_slots_set - old_slots_set, key=lambda x: (str(x[0]), x[1], x[2]))
    removed_slots = old_slots_set - new_slots_set

    # Check DB conflict on added slots
    if added_slots:
        added_hours = [h for _, _, h in added_slots]
        conflict_slot = await db.scalar(
            select(BookingSlot).where(
                BookingSlot.court_id == payload.court_id,
                BookingSlot.play_date == payload.play_date,
                BookingSlot.start_hour.in_(added_hours),
                BookingSlot.slot_status.in_(["LOCKED", "BOOKED"]),
                BookingSlot.booking_id != order.id,
            )
        )
        if conflict_slot:
            BOOKINGS_RESCHEDULED_TOTAL.labels(outcome="conflict").inc()
            raise HTTPException(
                status_code=409,
                detail=f"Khung giờ {conflict_slot.start_hour:02d}:00 - {conflict_slot.end_hour:02d}:00 đã có người đặt",
            )

    lock_token = order.lock_token or str(uuid.uuid4())
    acquired_keys: list[str] = []
    try:
        for cid, pdate, hr in added_slots:
            key = _slot_lock_key(cid, pdate, hr)
            try:
                ok = await redis_client.set(key, lock_token, nx=True, ex=settings.lock_ttl_seconds)
                if not ok:
                    BOOKING_CONFLICTS_TOTAL.labels(source="redis").inc()
                    BOOKINGS_RESCHEDULED_TOTAL.labels(outcome="conflict").inc()
                    raise HTTPException(
                        status_code=409,
                        detail=f"Khung giờ {hr:02d}:00 - {hr + 1:02d}:00 đang được giữ bởi giao dịch khác",
                    )
                acquired_keys.append(key)
            except RedisError as exc:
                REDIS_LOCK_FAILURES_TOTAL.inc()
                logger.warning("Redis unavailable during reschedule lock acquire for %s: %s", key, exc)

        # Atomic slot transfer in DB: release removed slots, keep overlapping, insert added
        target_slot_status = "BOOKED" if order.status == "PAID" else "LOCKED"
        for s in order.slots:
            if (s.court_id, s.play_date, s.start_hour) in removed_slots:
                s.slot_status = "RELEASED"

        for cid, pdate, hr in added_slots:
            price, is_peak = new_slot_prices[hr]
            db.add(
                BookingSlot(
                    booking_id=order.id,
                    court_id=cid,
                    play_date=pdate,
                    start_hour=hr,
                    end_hour=hr + 1,
                    slot_price=price,
                    is_peak_hour=is_peak,
                    slot_status=target_slot_status,
                )
            )

        prev_rev = order.booking_revision
        new_rev = prev_rev + 1
        prev_court_id = order.court_id
        prev_court_name = order.court_name_snapshot
        prev_play_date = order.play_date
        prev_start = order.start_hour
        prev_end = order.end_hour
        prev_amount = order.total_amount

        new_court_info = serialize_court(new_court)
        order.court_id = new_court.id
        order.court_name_snapshot = new_court.name
        order.branch_name_snapshot = new_court_info.branch_name
        order.location_name_snapshot = new_court_info.location_name
        order.location_address_snapshot = new_court_info.location_address
        order.play_date = payload.play_date
        order.start_hour = payload.hours[0]
        order.end_hour = payload.hours[-1] + 1
        order.total_amount = new_amount
        order.booking_revision = new_rev
        order.lock_token = lock_token

        db.add(
            BookingRescheduleHistory(
                booking_id=order.id,
                booking_code=order.booking_code,
                idempotency_key=payload.idempotency_key,
                previous_revision=prev_rev,
                new_revision=new_rev,
                previous_court_id=prev_court_id,
                previous_court_name=prev_court_name,
                previous_play_date=prev_play_date,
                previous_start_hour=prev_start,
                previous_end_hour=prev_end,
                previous_amount=prev_amount,
                new_court_id=new_court.id,
                new_court_name=new_court.name,
                new_play_date=payload.play_date,
                new_start_hour=payload.hours[0],
                new_end_hour=payload.hours[-1] + 1,
                new_amount=new_amount,
                actor=actor,
                actor_role=actor_role,
                reason=payload.reason,
            )
        )
        record_operational_audit(
            db,
            entity_type="BOOKING",
            entity_id=order.booking_code,
            action="BOOKING_RESCHEDULED",
            actor=actor,
            actor_role=actor_role,
            previous_state=f"{prev_court_name} {prev_play_date} {prev_start:02d}-{prev_end:02d} v{prev_rev}",
            new_state=f"{new_court.name} {payload.play_date} {payload.hours[0]:02d}-{payload.hours[-1]+1:02d} v{new_rev}",
            reason=payload.reason,
            metadata={"previous_amount": float(prev_amount), "new_amount": float(new_amount)},
        )
        enqueue_outbox_event(
            db,
            event_type="booking.rescheduled",
            aggregate_id=order.booking_code,
            payload={
                "booking_id": str(order.id),
                "booking_code": order.booking_code,
                "status": order.status,
                "previous_revision": prev_rev,
                "new_revision": new_rev,
                "court_name": new_court.name,
                "branch_name": new_court_info.branch_name,
                "location_name": new_court_info.location_name,
                "location_address": new_court_info.location_address,
                "play_date": payload.play_date.isoformat(),
                "start_hour": payload.hours[0],
                "end_hour": payload.hours[-1] + 1,
                "total_amount": float(new_amount),
                "customer_name": order.customer_name,
                "customer_email": order.customer_email,
                "customer_phone": order.customer_phone,
            },
        )
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            BOOKING_CONFLICTS_TOTAL.labels(source="postgres").inc()
            BOOKINGS_RESCHEDULED_TOTAL.labels(outcome="conflict").inc()
            raise HTTPException(
                status_code=409,
                detail="Khung giờ mới vừa được đặt bởi giao dịch khác",
            ) from exc
    except Exception:
        if acquired_keys:
            await release_owned_locks(redis_client, acquired_keys, lock_token)
        raise

    # Release old Redis locks for removed slots after commit
    if removed_slots:
        old_keys = [_slot_lock_key(cid, pdate, hr) for cid, pdate, hr in removed_slots]
        await release_owned_locks(redis_client, old_keys, lock_token)

    if order.status == "PENDING_PAYMENT":
        await _sync_payment_revision(order.booking_code, int(round(float(new_amount))), new_rev)

    BOOKINGS_RESCHEDULED_TOTAL.labels(outcome="success").inc()
    reloaded = await _reload_booking(db, order.id)
    return BookingResponse.model_validate(reloaded)


async def create_maintenance_block(
    db: AsyncSession,
    redis_client: Redis,
    payload: CreateMaintenanceRequest,
    *,
    actor_email: str,
    actor_role: str,
) -> MaintenanceBlockResponse:
    if payload.end_hour <= payload.start_hour:
        raise HTTPException(status_code=400, detail="Giờ kết thúc bảo trì phải lớn hơn giờ bắt đầu")

    if payload.idempotency_key:
        existing_idem = await db.scalar(
            select(MaintenanceBlock).where(MaintenanceBlock.idempotency_key == payload.idempotency_key)
        )
        if existing_idem:
            return MaintenanceBlockResponse.model_validate(existing_idem)

    # Authoritative PostgreSQL FOR UPDATE lock on Court row serializes Maintenance vs Booking/Reschedule
    court = await db.scalar(
        select(Court).where(Court.id == payload.court_id, Court.is_deleted.is_(False)).with_for_update()
    )
    if not court:
        raise HTTPException(status_code=404, detail="Không tìm thấy sân")

    hours = list(range(payload.start_hour, payload.end_hour))
    conflict_slot = await db.scalar(
        select(BookingSlot).where(
            BookingSlot.court_id == payload.court_id,
            BookingSlot.play_date == payload.play_date,
            BookingSlot.start_hour.in_(hours),
            BookingSlot.slot_status.in_(["LOCKED", "BOOKED"]),
        )
    )
    if conflict_slot:
        MAINTENANCE_BLOCKS_TOTAL.labels(action="conflict").inc()
        raise HTTPException(
            status_code=409,
            detail=f"Không thể tạo lịch bảo trì vì khung giờ {conflict_slot.start_hour:02d}:00 - {conflict_slot.end_hour:02d}:00 đã có đơn đặt sân hoạt động",
        )

    overlap_maint = await db.scalar(
        select(MaintenanceBlock).where(
            MaintenanceBlock.court_id == payload.court_id,
            MaintenanceBlock.play_date == payload.play_date,
            MaintenanceBlock.status == "SCHEDULED",
            MaintenanceBlock.start_hour < payload.end_hour,
            MaintenanceBlock.end_hour > payload.start_hour,
        )
    )
    if overlap_maint:
        MAINTENANCE_BLOCKS_TOTAL.labels(action="conflict").inc()
        raise HTTPException(
            status_code=409,
            detail=f"Khung giờ bảo trì bị trùng với lịch bảo trì đã tạo ({overlap_maint.start_hour:02d}:00 - {overlap_maint.end_hour:02d}:00)",
        )

    block = MaintenanceBlock(
        court_id=court.id,
        court_name_snapshot=court.name,
        play_date=payload.play_date,
        start_hour=payload.start_hour,
        end_hour=payload.end_hour,
        reason=payload.reason.strip(),
        status="SCHEDULED",
        idempotency_key=payload.idempotency_key,
        created_by=actor_email,
    )
    db.add(block)
    await db.flush()
    record_operational_audit(
        db,
        entity_type="MAINTENANCE",
        entity_id=str(block.id),
        action="MAINTENANCE_SCHEDULED",
        actor=actor_email,
        actor_role=actor_role,
        previous_state=None,
        new_state="SCHEDULED",
        reason=payload.reason.strip(),
        metadata={
            "court_name": court.name,
            "play_date": payload.play_date.isoformat(),
            "start_hour": payload.start_hour,
            "end_hour": payload.end_hour,
        },
    )
    enqueue_outbox_event(
        db,
        event_type="court.maintenance_scheduled",
        aggregate_id=str(court.id),
        payload={
            "maintenance_id": str(block.id),
            "court_id": str(court.id),
            "court_name": court.name,
            "play_date": payload.play_date.isoformat(),
            "start_hour": payload.start_hour,
            "end_hour": payload.end_hour,
            "reason": payload.reason.strip(),
        },
    )
    await db.commit()
    await db.refresh(block)
    MAINTENANCE_BLOCKS_TOTAL.labels(action="scheduled").inc()
    return MaintenanceBlockResponse.model_validate(block)


async def cancel_maintenance_block(
    db: AsyncSession,
    block_id: uuid.UUID,
    *,
    actor_email: str,
    actor_role: str,
) -> MaintenanceBlockResponse:
    block = await db.scalar(
        select(MaintenanceBlock).where(MaintenanceBlock.id == block_id).with_for_update()
    )
    if not block:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch bảo trì")
    if block.status == "CANCELLED":
        return MaintenanceBlockResponse.model_validate(block)
    if block.status != "SCHEDULED":
        raise HTTPException(status_code=400, detail=f"Không thể hủy lịch bảo trì ở trạng thái {block.status}")

    now_utc = datetime.now(timezone.utc)
    block.status = "CANCELLED"
    block.cancelled_by = actor_email
    block.cancelled_at = now_utc
    block.updated_at = now_utc
    record_operational_audit(
        db,
        entity_type="MAINTENANCE",
        entity_id=str(block.id),
        action="MAINTENANCE_CANCELLED",
        actor=actor_email,
        actor_role=actor_role,
        previous_state="SCHEDULED",
        new_state="CANCELLED",
        reason="Hủy lịch bảo trì sân",
    )
    enqueue_outbox_event(
        db,
        event_type="court.maintenance_cancelled",
        aggregate_id=str(block.court_id),
        payload={
            "maintenance_id": str(block.id),
            "court_id": str(block.court_id),
            "play_date": block.play_date.isoformat(),
            "start_hour": block.start_hour,
            "end_hour": block.end_hour,
        },
    )
    await db.commit()
    await db.refresh(block)
    MAINTENANCE_BLOCKS_TOTAL.labels(action="cancelled").inc()
    return MaintenanceBlockResponse.model_validate(block)


async def mark_booking_no_show(
    db: AsyncSession,
    booking_code: str,
    payload: NoShowRequest,
    *,
    actor_email: str,
    actor_role: str,
) -> BookingResponse:
    order = await db.scalar(
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .where(BookingOrder.booking_code == booking_code.strip())
        .with_for_update()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt sân")
    if order.status == "NO_SHOW":
        return BookingResponse.model_validate(order)
    if order.admission_status == "ADMITTED":
        raise HTTPException(status_code=409, detail="Khách đã check-in vào sân, không thể đánh dấu NO_SHOW")
    if order.status != "PAID":
        raise HTTPException(status_code=400, detail=f"Chỉ đơn PAID chưa check-in mới được đánh dấu NO_SHOW (hiện tại: {order.status})")

    grace = (
        payload.grace_minutes_override
        if (payload.grace_minutes_override is not None and settings.app_env.lower() != "production")
        else settings.no_show_grace_minutes
    )
    now_vn = datetime.now(VN_TZ)
    eligible_at = datetime.combine(order.play_date, dt_time(order.start_hour, 0), tzinfo=VN_TZ) + timedelta(minutes=grace)
    if now_vn < eligible_at:
        raise HTTPException(
            status_code=400,
            detail=f"Chưa qua thời gian chờ ({grace} phút sau giờ bắt đầu). Có thể đánh dấu no-show sau {eligible_at.strftime('%H:%M %d/%m/%Y')}",
        )

    now_utc = datetime.now(timezone.utc)
    order.status = "NO_SHOW"
    order.no_show_at = now_utc
    order.no_show_by = actor_email
    record_operational_audit(
        db,
        entity_type="BOOKING",
        entity_id=order.booking_code,
        action="BOOKING_MARKED_NO_SHOW",
        actor=actor_email,
        actor_role=actor_role,
        previous_state="PAID",
        new_state="NO_SHOW",
        reason=payload.reason,
    )
    enqueue_outbox_event(
        db,
        event_type="booking.no_show",
        aggregate_id=order.booking_code,
        payload={
            "booking_id": str(order.id),
            "booking_code": order.booking_code,
            "customer_name": order.customer_name,
            "customer_email": order.customer_email,
            "court_name": order.court_name_snapshot,
            "play_date": order.play_date.isoformat(),
            "start_hour": order.start_hour,
            "end_hour": order.end_hour,
            "reason": payload.reason,
        },
    )
    await db.commit()
    BOOKINGS_LIFECYCLE_TOTAL.labels(status="NO_SHOW").inc()
    reloaded = await _reload_booking(db, order.id)
    return BookingResponse.model_validate(reloaded)


async def complete_booking(
    db: AsyncSession,
    booking_code: str,
    payload: CompleteBookingRequest,
    *,
    actor_email: str,
    actor_role: str,
) -> BookingResponse:
    order = await db.scalar(
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .where(BookingOrder.booking_code == booking_code.strip())
        .with_for_update()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt sân")
    if order.status == "COMPLETED":
        return BookingResponse.model_validate(order)
    if order.status != "PAID" or order.admission_status != "ADMITTED":
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ có thể hoàn tất đơn PAID đã check-in (status={order.status}, admission={order.admission_status})",
        )

    now_vn = datetime.now(VN_TZ)
    end_h = order.end_hour if order.end_hour < 24 else 23
    end_m = 0 if order.end_hour < 24 else 59
    slot_end_vn = datetime.combine(order.play_date, dt_time(end_h, end_m), tzinfo=VN_TZ)
    if now_vn < slot_end_vn:
        if not payload.early_completion or len((payload.reason or "").strip()) < 5:
            raise HTTPException(
                status_code=400,
                detail="Chưa hết giờ chơi. Hoàn tất sớm cần bật early_completion và nhập lý do (>= 5 ký tự).",
            )

    now_utc = datetime.now(timezone.utc)
    order.status = "COMPLETED"
    order.completed_at = now_utc
    order.completed_by = actor_email
    record_operational_audit(
        db,
        entity_type="BOOKING",
        entity_id=order.booking_code,
        action="BOOKING_COMPLETED",
        actor=actor_email,
        actor_role=actor_role,
        previous_state="PAID",
        new_state="COMPLETED",
        reason=payload.reason,
        metadata={"early_completion": payload.early_completion},
    )
    enqueue_outbox_event(
        db,
        event_type="booking.completed",
        aggregate_id=order.booking_code,
        payload={
            "booking_id": str(order.id),
            "booking_code": order.booking_code,
            "customer_name": order.customer_name,
            "customer_email": order.customer_email,
            "court_name": order.court_name_snapshot,
            "play_date": order.play_date.isoformat(),
            "start_hour": order.start_hour,
            "end_hour": order.end_hour,
        },
    )
    await db.commit()
    BOOKINGS_LIFECYCLE_TOTAL.labels(status="COMPLETED").inc()
    reloaded = await _reload_booking(db, order.id)
    return BookingResponse.model_validate(reloaded)
