import asyncio
import json
import logging
import secrets
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import aio_pika
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import AsyncSessionLocal
from app.events.rabbitmq import rmq_client
from app.metrics import BOOKINGS_CREATED_TOTAL, BOOKINGS_EXPIRED_TOTAL, BOOKINGS_PAID_TOTAL
from app.models import BookingOrder, BookingSlot, Branch, Court, Location, PricingRule
from app.schemas import (
    AdminStatsResponse,
    AvailabilityResponse,
    AvailabilitySlotItem,
    BookingResponse,
    BranchResponse,
    CourtAvailabilityItem,
    CourtResponse,
    CreateBookingRequest,
    LocationResponse,
)

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def format_branch_name(branch: Branch) -> str:
    suffix = f" - {branch.title_note.strip()}" if branch.title_note and branch.title_note.strip() else ""
    return f"Chi nhánh {branch.branch_number}{suffix}"


def serialize_location(loc: Location, branch: Branch | None = None) -> LocationResponse:
    b = branch or loc.branch
    b_num = b.branch_number if b else 0
    b_name = format_branch_name(b) if b else ""
    active_courts = [c for c in (loc.courts or []) if not c.is_deleted]
    return LocationResponse(
        id=loc.id,
        branch_id=loc.branch_id,
        branch_number=b_num,
        branch_name=b_name,
        name=loc.name,
        address=loc.address,
        court_count=len(active_courts),
        created_at=loc.created_at,
    )


def serialize_branch(branch: Branch) -> BranchResponse:
    active_locs = sorted(
        [loc for loc in (branch.locations or []) if not loc.is_deleted],
        key=lambda x: x.created_at,
    )
    return BranchResponse(
        id=branch.id,
        branch_number=branch.branch_number,
        title_note=branch.title_note,
        display_name=format_branch_name(branch),
        locations=[serialize_location(loc, branch) for loc in active_locs],
        created_at=branch.created_at,
    )


def serialize_court(court: Court) -> CourtResponse:
    loc = court.location if court.location and not court.location.is_deleted else None
    branch = loc.branch if loc and loc.branch and not loc.branch.is_deleted else None
    return CourtResponse(
        id=court.id,
        location_id=loc.id if loc else None,
        branch_id=branch.id if branch else None,
        branch_number=branch.branch_number if branch else None,
        branch_name=format_branch_name(branch) if branch else "",
        location_name=loc.name if loc else "",
        location_address=loc.address if loc else "",
        name=court.name,
        court_type=court.court_type,
        surface=court.surface,
        status=court.status,
        description=court.description,
        created_at=court.created_at,
    )


async def _reload_booking(db: AsyncSession, booking_id: uuid.UUID) -> BookingOrder:
    stmt = (
        select(BookingOrder)
        .options(selectinload(BookingOrder.slots))
        .execution_options(populate_existing=True)
        .where(BookingOrder.id == booking_id)
    )
    order = await db.scalar(stmt)
    assert order is not None
    return order


def _slot_lock_key(court_id: uuid.UUID, play_date: date, start_hour: int) -> str:
    return f"lock:court:{court_id}:{play_date.isoformat()}:{start_hour}"


def _generate_booking_code(play_date: date) -> str:
    suffix = secrets.token_hex(2).upper()
    return f"PKB-{play_date.strftime('%Y%m%d')}-{suffix}"


async def seed_courts_and_pricing(db: AsyncSession) -> None:
    existing_branches = await db.scalar(select(func.count()).select_from(Branch))
    default_loc_1a: Location | None = None
    default_loc_1b: Location | None = None
    default_loc_2a: Location | None = None

    if not existing_branches:
        b1 = Branch(branch_number=1, title_note="Khu vực Nam Sài Gòn")
        b2 = Branch(branch_number=2, title_note="Khu vực TP. Thủ Đức")
        db.add_all([b1, b2])
        await db.flush()

        default_loc_1a = Location(
            branch_id=b1.id,
            name="Cơ sở Nguyễn Thị Thập",
            address="120 Nguyễn Thị Thập, Phường Bình Thuận, Quận 7, TP.HCM",
        )
        default_loc_1b = Location(
            branch_id=b1.id,
            name="Cơ sở Phú Mỹ Hưng",
            address="45 Tân Phú, Khu đô thị Phú Mỹ Hưng, Quận 7, TP.HCM",
        )
        default_loc_2a = Location(
            branch_id=b2.id,
            name="Cơ sở Thảo Điền",
            address="88 Xuân Thủy, Phường Thảo Điền, TP. Thủ Đức, TP.HCM",
        )
        db.add_all([default_loc_1a, default_loc_1b, default_loc_2a])
        await db.flush()
    else:
        default_loc_1a = await db.scalar(
            select(Location).where(Location.is_deleted.is_(False)).order_by(Location.created_at)
        )

    existing_courts = await db.scalar(select(func.count()).select_from(Court))
    if not existing_courts and default_loc_1a:
        loc_b = default_loc_1b or default_loc_1a
        loc_c = default_loc_2a or default_loc_1a
        courts = [
            Court(
                location_id=default_loc_1a.id,
                name="Sân 01 - Trong nhà VIP",
                court_type="INDOOR",
                surface="Acrylic 7 lớp chuẩn USAPA",
                status="ACTIVE",
                description="Sân có mái che, hệ thống đèn LED chống chói và khu nghỉ mát.",
            ),
            Court(
                location_id=default_loc_1a.id,
                name="Sân 02 - Trong nhà Tiêu chuẩn",
                court_type="INDOOR",
                surface="Acrylic 7 lớp chuẩn USAPA",
                status="ACTIVE",
                description="Sân thi đấu trong nhà phù hợp tập luyện và giao lưu nhóm.",
            ),
            Court(
                location_id=loc_b.id,
                name="Sân 03 - Ngoài trời A",
                court_type="OUTDOOR",
                surface="Asphalt phủ sơn thể thao chống trượt",
                status="ACTIVE",
                description="Sân ngoài trời thoáng mát, không gian mở.",
            ),
            Court(
                location_id=loc_c.id,
                name="Sân 04 - Ngoài trời B",
                court_type="OUTDOOR",
                surface="Asphalt phủ sơn thể thao chống trượt",
                status="ACTIVE",
                description="Sân ngoài trời tiêu chuẩn phù hợp người mới và giải phong trào.",
            ),
        ]
        db.add_all(courts)
    elif default_loc_1a:
        # Backfill existing pre-migration courts & bookings if location_id is null
        await db.execute(
            update(Court).where(Court.location_id.is_(None)).values(location_id=default_loc_1a.id)
        )
        branch_1 = await db.scalar(select(Branch).where(Branch.id == default_loc_1a.branch_id))
        b_label = format_branch_name(branch_1) if branch_1 else "Chi nhánh 1"
        await db.execute(
            update(BookingOrder)
            .where(BookingOrder.location_name_snapshot == "")
            .values(
                branch_name_snapshot=b_label,
                location_name_snapshot=default_loc_1a.name,
                location_address_snapshot=default_loc_1a.address,
            )
        )

    existing_rules = await db.scalar(select(func.count()).select_from(PricingRule))
    if not existing_rules:
        rules = [
            PricingRule(court_type="INDOOR", start_hour=5, end_hour=16, is_weekend=False, is_peak_hour=False, price_per_hour=Decimal("150000")),
            PricingRule(court_type="INDOOR", start_hour=16, end_hour=22, is_weekend=False, is_peak_hour=True, price_per_hour=Decimal("220000")),
            PricingRule(court_type="OUTDOOR", start_hour=5, end_hour=16, is_weekend=False, is_peak_hour=False, price_per_hour=Decimal("100000")),
            PricingRule(court_type="OUTDOOR", start_hour=16, end_hour=22, is_weekend=False, is_peak_hour=True, price_per_hour=Decimal("160000")),
            PricingRule(court_type="INDOOR", start_hour=5, end_hour=16, is_weekend=True, is_peak_hour=False, price_per_hour=Decimal("180000")),
            PricingRule(court_type="INDOOR", start_hour=16, end_hour=22, is_weekend=True, is_peak_hour=True, price_per_hour=Decimal("250000")),
            PricingRule(court_type="OUTDOOR", start_hour=5, end_hour=16, is_weekend=True, is_peak_hour=False, price_per_hour=Decimal("120000")),
            PricingRule(court_type="OUTDOOR", start_hour=16, end_hour=22, is_weekend=True, is_peak_hour=True, price_per_hour=Decimal("190000")),
        ]
        db.add_all(rules)

    await db.commit()


def _find_slot_price(rules: list[PricingRule], court_type: str, is_weekend: bool, hour: int) -> tuple[Decimal, bool]:
    for r in rules:
        if r.court_type == court_type and r.is_weekend == is_weekend and r.start_hour <= hour < r.end_hour:
            return r.price_per_hour, r.is_peak_hour
    is_peak = hour >= 16
    return (Decimal("200000") if is_peak else Decimal("120000")), is_peak


async def get_availability(
    db: AsyncSession,
    play_date: date,
    branch_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
) -> AvailabilityResponse:
    is_weekend = play_date.weekday() >= 5
    stmt = (
        select(Court)
        .options(selectinload(Court.location).selectinload(Location.branch))
        .where(Court.is_deleted.is_(False))
        .order_by(Court.name)
    )
    if location_id:
        stmt = stmt.where(Court.location_id == location_id)
    elif branch_id:
        stmt = stmt.join(Location, Court.location_id == Location.id).where(
            Location.branch_id == branch_id,
            Location.is_deleted.is_(False),
        )

    courts = [
        c
        for c in (await db.scalars(stmt)).all()
        if (c.location is None) or (not c.location.is_deleted and (c.location.branch is None or not c.location.branch.is_deleted))
    ]
    rules = (await db.scalars(select(PricingRule))).all()
    slots_rows = (
        await db.scalars(
            select(BookingSlot).where(
                BookingSlot.play_date == play_date,
                BookingSlot.slot_status.in_(["LOCKED", "BOOKED"]),
            )
        )
    ).all()

    slot_map: dict[tuple[uuid.UUID, int], str] = {
        (s.court_id, s.start_hour): s.slot_status for s in slots_rows
    }

    now_vn = datetime.now(VN_TZ)
    court_items: list[CourtAvailabilityItem] = []
    for court in courts:
        items: list[AvailabilitySlotItem] = []
        for h in range(5, 22):
            price, is_peak = _find_slot_price(rules, court.court_type, is_weekend, h)
            slot_start_vn = datetime.combine(play_date, dt_time(h, 0), tzinfo=VN_TZ)
            if court.status != "ACTIVE":
                slot_status = "MAINTENANCE"
            elif (court.id, h) in slot_map:
                slot_status = slot_map[(court.id, h)]
            elif slot_start_vn <= now_vn:
                slot_status = "PAST"
            else:
                slot_status = "AVAILABLE"
            items.append(
                AvailabilitySlotItem(
                    start_hour=h,
                    end_hour=h + 1,
                    label=f"{h:02d}:00 - {h + 1:02d}:00",
                    price=float(price),
                    is_peak_hour=is_peak,
                    status=slot_status,  # type: ignore[arg-type]
                )
            )
        court_items.append(CourtAvailabilityItem(court=serialize_court(court), slots=items))

    return AvailabilityResponse(play_date=play_date, is_weekend=is_weekend, courts=court_items)


async def create_booking(
    db: AsyncSession,
    redis_client: Redis,
    payload: CreateBookingRequest,
    user_id: uuid.UUID | None,
) -> BookingResponse:
    now_vn = datetime.now(VN_TZ)
    if payload.play_date < now_vn.date():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể đặt sân cho ngày trong quá khứ")

    earliest_slot_vn = datetime.combine(payload.play_date, dt_time(payload.hours[0], 0), tzinfo=VN_TZ)
    if earliest_slot_vn <= now_vn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Khung giờ {payload.hours[0]:02d}:00 - {payload.hours[0] + 1:02d}:00 đã qua thời gian hiện tại "
                f"({now_vn.strftime('%H:%M')}), không thể đặt sân"
            ),
        )

    court = await db.scalar(
        select(Court)
        .options(selectinload(Court.location).selectinload(Location.branch))
        .where(Court.id == payload.court_id, Court.is_deleted.is_(False))
    )
    if not court:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sân")
    if court.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sân hiện đang bảo trì")

    court_info = serialize_court(court)
    is_weekend = payload.play_date.weekday() >= 5
    rules = (await db.scalars(select(PricingRule))).all()

    booking_code = _generate_booking_code(payload.play_date)
    acquired_keys: list[str] = []

    try:
        for h in payload.hours:
            key = _slot_lock_key(court.id, payload.play_date, h)
            ok = await redis_client.set(key, booking_code, nx=True, ex=settings.lock_ttl_seconds)
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Khung giờ {h:02d}:00 - {h + 1:02d}:00 đã có người khác giữ chỗ hoặc đặt rồi",
                )
            acquired_keys.append(key)

        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(seconds=settings.lock_ttl_seconds)
        total_amount = Decimal("0")
        slot_models: list[BookingSlot] = []

        for h in payload.hours:
            price, is_peak = _find_slot_price(rules, court.court_type, is_weekend, h)
            total_amount += price
            slot_models.append(
                BookingSlot(
                    court_id=court.id,
                    play_date=payload.play_date,
                    start_hour=h,
                    end_hour=h + 1,
                    slot_price=price,
                    is_peak_hour=is_peak,
                    slot_status="LOCKED",
                )
            )

        order = BookingOrder(
            booking_code=booking_code,
            user_id=user_id,
            customer_name=payload.customer_name.strip(),
            customer_phone=payload.customer_phone.strip(),
            customer_email=payload.customer_email.strip().lower(),
            court_id=court.id,
            court_name_snapshot=court.name,
            branch_name_snapshot=court_info.branch_name,
            location_name_snapshot=court_info.location_name,
            location_address_snapshot=court_info.location_address,
            play_date=payload.play_date,
            start_hour=payload.hours[0],
            end_hour=payload.hours[-1] + 1,
            total_amount=total_amount,
            status="PENDING_PAYMENT",
            expires_at=expires_at,
            slots=slot_models,
        )
        db.add(order)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Một hoặc nhiều khung giờ đã được đặt bởi giao dịch khác",
            ) from exc

        order = await _reload_booking(db, order.id)
        BOOKINGS_CREATED_TOTAL.labels(
            court_type=court.court_type,
            customer_type="registered" if user_id else "guest",
        ).inc()
        return BookingResponse.model_validate(order)
    except Exception:
        if acquired_keys:
            await redis_client.delete(*acquired_keys)
        raise


async def release_booking_slots(
    db: AsyncSession,
    redis_client: Redis,
    order: BookingOrder,
    new_status: str,
    reason: str | None = None,
) -> BookingResponse:
    order.status = new_status
    if reason:
        order.cancel_reason = reason
    await db.execute(
        update(BookingSlot)
        .where(BookingSlot.booking_id == order.id)
        .values(slot_status="RELEASED")
    )
    await db.commit()
    order = await _reload_booking(db, order.id)

    keys = [_slot_lock_key(order.court_id, order.play_date, s.start_hour) for s in order.slots]
    if keys:
        await redis_client.delete(*keys)

    event_name = "booking.expired" if new_status == "EXPIRED" else "booking.cancelled"
    await rmq_client.publish(
        event_name,
        {
            "event": event_name,
            "booking_id": str(order.id),
            "booking_code": order.booking_code,
            "status": new_status,
            "reason": reason,
        },
    )
    return BookingResponse.model_validate(order)


async def confirm_booking_paid(booking_code: str, redis_client: Redis) -> None:
    async with AsyncSessionLocal() as db:
        order = await db.scalar(
            select(BookingOrder)
            .options(selectinload(BookingOrder.slots))
            .where(BookingOrder.booking_code == booking_code)
        )
        if not order:
            logger.warning("payment.succeeded received for unknown booking_code=%s", booking_code)
            return
        if order.status == "PAID":
            return

        order.status = "PAID"
        order.paid_at = datetime.now(timezone.utc)
        await db.execute(
            update(BookingSlot)
            .where(BookingSlot.booking_id == order.id)
            .values(slot_status="BOOKED")
        )
        await db.commit()

        keys = [_slot_lock_key(order.court_id, order.play_date, s.start_hour) for s in order.slots]
        if keys:
            await redis_client.delete(*keys)

        BOOKINGS_PAID_TOTAL.inc()
        logger.info("Booking %s transitioned to PAID", booking_code)


async def start_payment_consumer(redis_client: Redis) -> None:
    if not rmq_client.channel or not rmq_client.exchange:
        return
    queue = await rmq_client.channel.declare_queue("booking.payment_events", durable=True)
    await queue.bind(rmq_client.exchange, routing_key="payment.succeeded")

    async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            data = json.loads(message.body.decode("utf-8"))
            booking_code = data.get("booking_code")
            if booking_code:
                await confirm_booking_paid(booking_code, redis_client)

    await queue.consume(_on_message)


async def run_expiration_worker(redis_client: Redis, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with AsyncSessionLocal() as db:
                now_utc = datetime.now(timezone.utc)
                expired_orders = (
                    await db.scalars(
                        select(BookingOrder)
                        .options(selectinload(BookingOrder.slots))
                        .where(
                            BookingOrder.status == "PENDING_PAYMENT",
                            BookingOrder.expires_at < now_utc,
                        )
                    )
                ).all()
                for order in expired_orders:
                    await release_booking_slots(
                        db, redis_client, order, "EXPIRED", "Hết thời gian giữ chỗ 15 phút"
                    )
                    BOOKINGS_EXPIRED_TOTAL.inc()
        except Exception as exc:
            logger.exception("Expiration worker error: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=15)
        except TimeoutError:
            continue


async def get_admin_stats(db: AsyncSession) -> AdminStatsResponse:
    total = await db.scalar(select(func.count()).select_from(BookingOrder)) or 0
    paid = await db.scalar(select(func.count()).select_from(BookingOrder).where(BookingOrder.status == "PAID")) or 0
    pending = (
        await db.scalar(select(func.count()).select_from(BookingOrder).where(BookingOrder.status == "PENDING_PAYMENT"))
        or 0
    )
    cancelled_expired = (
        await db.scalar(
            select(func.count())
            .select_from(BookingOrder)
            .where(BookingOrder.status.in_(["CANCELLED", "EXPIRED"]))
        )
        or 0
    )
    revenue = (
        await db.scalar(
            select(func.coalesce(func.sum(BookingOrder.total_amount), 0)).where(BookingOrder.status == "PAID")
        )
        or Decimal("0")
    )
    active_courts = (
        await db.scalar(
            select(func.count()).select_from(Court).where(Court.status == "ACTIVE", Court.is_deleted.is_(False))
        )
        or 0
    )
    return AdminStatsResponse(
        total_bookings=total,
        paid_bookings=paid,
        pending_bookings=pending,
        cancelled_or_expired=cancelled_expired,
        total_revenue=float(revenue),
        active_courts=active_courts,
    )
