import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Court, PricingRule
from app.schemas import (
    AvailabilityResponse,
    CourtCreateRequest,
    CourtResponse,
    CourtUpdateRequest,
    PricingRuleResponse,
    PricingRuleUpdateRequest,
)
from app.security import require_roles
from app.services.booking_service import get_availability

router = APIRouter(tags=["Courts & Pricing"])
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@router.get("/api/courts", response_model=list[CourtResponse])
async def list_courts(include_inactive: bool = False, db: AsyncSession = Depends(get_db)):
    stmt = select(Court).order_by(Court.name)
    if not include_inactive:
        stmt = stmt.where(Court.status == "ACTIVE")
    result = await db.scalars(stmt)
    return [CourtResponse.model_validate(c) for c in result.all()]


@router.get("/api/courts/availability", response_model=AvailabilityResponse)
async def court_availability(
    date_param: date | None = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    target_date = date_param or datetime.now(VN_TZ).date()
    return await get_availability(db, target_date)


@router.post("/api/courts", response_model=CourtResponse, status_code=status.HTTP_201_CREATED)
async def create_court(
    payload: CourtCreateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(select(Court).where(Court.name == payload.name.strip()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên sân đã tồn tại")
    court = Court(
        name=payload.name.strip(),
        court_type=payload.court_type,
        surface=payload.surface.strip(),
        description=payload.description.strip(),
    )
    db.add(court)
    await db.commit()
    await db.refresh(court)
    return CourtResponse.model_validate(court)


@router.patch("/api/courts/{court_id}", response_model=CourtResponse)
async def update_court(
    court_id: uuid.UUID,
    payload: CourtUpdateRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    court = await db.scalar(select(Court).where(Court.id == court_id))
    if not court:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sân")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(court, field, val)
    await db.commit()
    await db.refresh(court)
    return CourtResponse.model_validate(court)


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
