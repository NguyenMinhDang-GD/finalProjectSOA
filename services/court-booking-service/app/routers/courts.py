import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import BookingOrder, Branch, Court, Location, PricingRule
from app.schemas import (
    AvailabilityResponse,
    BranchCreateRequest,
    BranchResponse,
    BranchUpdateRequest,
    CourtCreateRequest,
    CourtResponse,
    CourtUpdateRequest,
    DeleteActionResponse,
    LocationCreateRequest,
    LocationResponse,
    LocationUpdateRequest,
    PricingRuleResponse,
    PricingRuleUpdateRequest,
)
from app.security import require_roles
from app.services.booking_service import (
    get_availability,
    serialize_branch,
    serialize_court,
    serialize_location,
)

router = APIRouter(tags=["Branches, Locations, Courts & Pricing"])
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


async def _load_branch_full(db: AsyncSession, branch_id: uuid.UUID) -> Branch | None:
    return await db.scalar(
        select(Branch)
        .options(selectinload(Branch.locations).selectinload(Location.courts))
        .execution_options(populate_existing=True)
        .where(Branch.id == branch_id, Branch.is_deleted.is_(False))
    )


async def _load_location_full(db: AsyncSession, location_id: uuid.UUID) -> Location | None:
    return await db.scalar(
        select(Location)
        .options(selectinload(Location.branch), selectinload(Location.courts))
        .execution_options(populate_existing=True)
        .where(Location.id == location_id, Location.is_deleted.is_(False))
    )


async def _load_court_full(db: AsyncSession, court_id: uuid.UUID) -> Court | None:
    return await db.scalar(
        select(Court)
        .options(selectinload(Court.location).selectinload(Location.branch))
        .execution_options(populate_existing=True)
        .where(Court.id == court_id, Court.is_deleted.is_(False))
    )


async def _has_upcoming_bookings(db: AsyncSession, court_ids: list[uuid.UUID]) -> bool:
    if not court_ids:
        return False
    today_vn = datetime.now(VN_TZ).date()
    cnt = await db.scalar(
        select(func.count())
        .select_from(BookingOrder)
        .where(
            BookingOrder.court_id.in_(court_ids),
            BookingOrder.status.in_(["PENDING_PAYMENT", "PAID"]),
            BookingOrder.play_date >= today_vn,
        )
    )
    return bool(cnt and cnt > 0)


async def _has_any_bookings(db: AsyncSession, court_ids: list[uuid.UUID]) -> bool:
    if not court_ids:
        return False
    cnt = await db.scalar(
        select(func.count()).select_from(BookingOrder).where(BookingOrder.court_id.in_(court_ids))
    )
    return bool(cnt and cnt > 0)


# -------------------- BRANCHES --------------------

@router.get("/api/branches", response_model=list[BranchResponse])
async def list_branches(db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(Branch)
        .options(selectinload(Branch.locations).selectinload(Location.courts))
        .where(Branch.is_deleted.is_(False))
        .order_by(Branch.branch_number)
    )
    return [serialize_branch(b) for b in rows.all()]


@router.post("/api/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    payload: BranchCreateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    max_num = await db.scalar(select(func.coalesce(func.max(Branch.branch_number), 0))) or 0
    branch = Branch(
        branch_number=int(max_num) + 1,
        title_note=payload.title_note.strip(),
    )
    db.add(branch)
    await db.commit()
    loaded = await _load_branch_full(db, branch.id)
    assert loaded is not None
    return serialize_branch(loaded)


@router.patch("/api/branches/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    branch = await _load_branch_full(db, branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chi nhánh")
    branch.title_note = payload.title_note.strip()
    await db.commit()
    loaded = await _load_branch_full(db, branch.id)
    assert loaded is not None
    return serialize_branch(loaded)


@router.delete("/api/branches/{branch_id}", response_model=DeleteActionResponse)
async def delete_branch(
    branch_id: uuid.UUID,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    branch = await db.scalar(select(Branch).where(Branch.id == branch_id, Branch.is_deleted.is_(False)))
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chi nhánh")

    loc_ids = list((await db.scalars(select(Location.id).where(Location.branch_id == branch_id))).all())
    court_ids = (
        list((await db.scalars(select(Court.id).where(Court.location_id.in_(loc_ids)))).all()) if loc_ids else []
    )

    if await _has_upcoming_bookings(db, court_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chi nhánh đang có đơn đặt sân sắp tới, không thể xóa. Vui lòng xử lý đơn đặt trước.",
        )

    if await _has_any_bookings(db, court_ids):
        if court_ids:
            await db.execute(
                update(Court).where(Court.id.in_(court_ids)).values(is_deleted=True, status="MAINTENANCE")
            )
        if loc_ids:
            await db.execute(update(Location).where(Location.id.in_(loc_ids)).values(is_deleted=True))
        branch.is_deleted = True
        await db.commit()
        return DeleteActionResponse(
            deleted=True,
            mode="soft",
            message=f"Đã ẩn Chi nhánh {branch.branch_number} (giữ lại lịch sử đơn đặt cũ)",
        )

    if court_ids:
        await db.execute(delete(Court).where(Court.id.in_(court_ids)))
    if loc_ids:
        await db.execute(delete(Location).where(Location.id.in_(loc_ids)))
    await db.delete(branch)
    await db.commit()
    return DeleteActionResponse(deleted=True, mode="hard", message=f"Đã xóa hoàn toàn Chi nhánh {branch.branch_number}")


# -------------------- LOCATIONS --------------------

@router.get("/api/locations", response_model=list[LocationResponse])
async def list_locations(branch_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Location)
        .options(selectinload(Location.branch), selectinload(Location.courts))
        .where(Location.is_deleted.is_(False))
        .order_by(Location.created_at)
    )
    if branch_id:
        stmt = stmt.where(Location.branch_id == branch_id)
    rows = (await db.scalars(stmt)).all()
    return [serialize_location(loc) for loc in rows if not loc.branch.is_deleted]


@router.post("/api/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    branch = await db.scalar(select(Branch).where(Branch.id == payload.branch_id, Branch.is_deleted.is_(False)))
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chi nhánh")

    dup = await db.scalar(
        select(Location).where(
            Location.branch_id == payload.branch_id,
            Location.name == payload.name.strip(),
            Location.is_deleted.is_(False),
        )
    )
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên địa điểm đã tồn tại trong chi nhánh này")

    loc = Location(
        branch_id=payload.branch_id,
        name=payload.name.strip(),
        address=payload.address.strip(),
    )
    db.add(loc)
    await db.commit()
    loaded = await _load_location_full(db, loc.id)
    assert loaded is not None
    return serialize_location(loaded)


@router.patch("/api/locations/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: uuid.UUID,
    payload: LocationUpdateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    loc = await _load_location_full(db, location_id)
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy địa điểm")

    updates = payload.model_dump(exclude_unset=True)
    if "branch_id" in updates and updates["branch_id"]:
        target_b = await db.scalar(
            select(Branch).where(Branch.id == updates["branch_id"], Branch.is_deleted.is_(False))
        )
        if not target_b:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chi nhánh đích không tồn tại")

    for field, val in updates.items():
        if isinstance(val, str):
            val = val.strip()
        setattr(loc, field, val)
    await db.commit()
    loaded = await _load_location_full(db, loc.id)
    assert loaded is not None
    return serialize_location(loaded)


@router.delete("/api/locations/{location_id}", response_model=DeleteActionResponse)
async def delete_location(
    location_id: uuid.UUID,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    loc = await db.scalar(select(Location).where(Location.id == location_id, Location.is_deleted.is_(False)))
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy địa điểm")

    court_ids = list((await db.scalars(select(Court.id).where(Court.location_id == location_id))).all())
    if await _has_upcoming_bookings(db, court_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Địa điểm này đang có đơn đặt sân sắp tới, không thể xóa.",
        )

    if await _has_any_bookings(db, court_ids):
        if court_ids:
            await db.execute(
                update(Court).where(Court.id.in_(court_ids)).values(is_deleted=True, status="MAINTENANCE")
            )
        loc.is_deleted = True
        await db.commit()
        return DeleteActionResponse(
            deleted=True,
            mode="soft",
            message=f"Đã ẩn địa điểm '{loc.name}' (giữ lại lịch sử đơn đặt cũ)",
        )

    if court_ids:
        await db.execute(delete(Court).where(Court.id.in_(court_ids)))
    await db.delete(loc)
    await db.commit()
    return DeleteActionResponse(deleted=True, mode="hard", message=f"Đã xóa hoàn toàn địa điểm '{loc.name}'")


# -------------------- COURTS --------------------

@router.get("/api/courts", response_model=list[CourtResponse])
async def list_courts(
    include_inactive: bool = False,
    branch_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Court)
        .options(selectinload(Court.location).selectinload(Location.branch))
        .where(Court.is_deleted.is_(False))
        .order_by(Court.name)
    )
    if not include_inactive:
        stmt = stmt.where(Court.status == "ACTIVE")
    if location_id:
        stmt = stmt.where(Court.location_id == location_id)
    elif branch_id:
        stmt = stmt.join(Location, Court.location_id == Location.id).where(
            Location.branch_id == branch_id,
            Location.is_deleted.is_(False),
        )
    result = await db.scalars(stmt)
    return [serialize_court(c) for c in result.all()]


@router.get("/api/courts/availability", response_model=AvailabilityResponse)
async def court_availability(
    date_param: date | None = Query(default=None, alias="date"),
    branch_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    target_date = date_param or datetime.now(VN_TZ).date()
    return await get_availability(db, target_date, branch_id=branch_id, location_id=location_id)


@router.post("/api/courts", response_model=CourtResponse, status_code=status.HTTP_201_CREATED)
async def create_court(
    payload: CourtCreateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    loc = await db.scalar(select(Location).where(Location.id == payload.location_id, Location.is_deleted.is_(False)))
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Địa điểm đã chọn không tồn tại")

    existing = await db.scalar(
        select(Court).where(
            Court.location_id == payload.location_id,
            Court.name == payload.name.strip(),
            Court.is_deleted.is_(False),
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên sân đã tồn tại tại địa điểm này")

    court = Court(
        location_id=payload.location_id,
        name=payload.name.strip(),
        court_type=payload.court_type,
        surface=payload.surface.strip(),
        description=payload.description.strip(),
    )
    db.add(court)
    await db.commit()
    loaded = await _load_court_full(db, court.id)
    assert loaded is not None
    return serialize_court(loaded)


@router.patch("/api/courts/{court_id}", response_model=CourtResponse)
async def update_court(
    court_id: uuid.UUID,
    payload: CourtUpdateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    court = await _load_court_full(db, court_id)
    if not court:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sân")

    updates = payload.model_dump(exclude_unset=True)
    target_location_id = updates.get("location_id", court.location_id)
    if "location_id" in updates and updates["location_id"]:
        loc = await db.scalar(
            select(Location).where(Location.id == updates["location_id"], Location.is_deleted.is_(False))
        )
        if not loc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Địa điểm đích không tồn tại")

    if "name" in updates and updates["name"]:
        new_name = updates["name"].strip()
        dup = await db.scalar(
            select(Court).where(
                Court.location_id == target_location_id,
                Court.name == new_name,
                Court.id != court_id,
                Court.is_deleted.is_(False),
            )
        )
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên sân đã tồn tại tại địa điểm này")

    for field, val in updates.items():
        if isinstance(val, str):
            val = val.strip()
        setattr(court, field, val)
    await db.commit()
    loaded = await _load_court_full(db, court.id)
    assert loaded is not None
    return serialize_court(loaded)


@router.delete("/api/courts/{court_id}", response_model=DeleteActionResponse)
async def delete_court(
    court_id: uuid.UUID,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    court = await db.scalar(select(Court).where(Court.id == court_id, Court.is_deleted.is_(False)))
    if not court:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sân")

    if await _has_upcoming_bookings(db, [court_id]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sân đang có đơn đặt sắp tới (chờ thanh toán hoặc đã thanh toán), không thể xóa. Vui lòng chuyển sang Bảo trì hoặc hủy đơn trước.",
        )

    if await _has_any_bookings(db, [court_id]):
        court.is_deleted = True
        court.status = "MAINTENANCE"
        await db.commit()
        return DeleteActionResponse(
            deleted=True,
            mode="soft",
            message=f"Đã xóa mềm sân '{court.name}' (giữ lại dữ liệu thống kê đơn đặt cũ)",
        )

    await db.delete(court)
    await db.commit()
    return DeleteActionResponse(deleted=True, mode="hard", message=f"Đã xóa hoàn toàn sân '{court.name}'")


# -------------------- PRICING RULES --------------------

@router.get("/api/pricing-rules", response_model=list[PricingRuleResponse])
async def list_pricing_rules(db: AsyncSession = Depends(get_db)):
    rules = await db.scalars(
        select(PricingRule).order_by(PricingRule.court_type, PricingRule.is_weekend, PricingRule.start_hour)
    )
    return [PricingRuleResponse.model_validate(r) for r in rules.all()]


@router.put("/api/pricing-rules/{rule_id}", response_model=PricingRuleResponse)
async def update_pricing_rule(
    rule_id: uuid.UUID,
    payload: PricingRuleUpdateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    rule = await db.scalar(select(PricingRule).where(PricingRule.id == rule_id))
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy quy tắc giá")
    rule.price_per_hour = payload.price_per_hour
    await db.commit()
    await db.refresh(rule)
    return PricingRuleResponse.model_validate(rule)
