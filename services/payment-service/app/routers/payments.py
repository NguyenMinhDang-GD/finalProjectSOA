import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import PaymentTransaction
from app.schemas import CreatePaymentRequest, PaymentResponse, PaymentWebhookRequest
from app.security import authorize_booking_access, get_optional_claims, is_valid_internal_key
from app.services.payment_service import (
    confirm_payment_idempotent,
    create_or_get_payment,
    verify_webhook_signature,
)

router = APIRouter(prefix="/api/payments", tags=["Payments & VietQR"])


@router.post("/create", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: CreatePaymentRequest,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    await authorize_booking_access(payload.booking_code, claims, x_guest_token)
    return await create_or_get_payment(db, payload.booking_code)


@router.get("/booking/{booking_code}", response_model=PaymentResponse)
async def get_payment_by_booking(
    booking_code: str,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    await authorize_booking_access(booking_code, claims, x_guest_token)
    tx = await db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.booking_code == booking_code.strip())
    )
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có giao dịch thanh toán cho đơn này")
    return PaymentResponse.model_validate(tx)


@router.post("/webhook", response_model=PaymentResponse)
async def payment_webhook(
    payload: PaymentWebhookRequest,
    x_webhook_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verify_webhook_signature(
        payload.booking_code, payload.amount, payload.provider_tx_id, x_webhook_signature
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chữ ký Webhook không hợp lệ")
    return await confirm_payment_idempotent(
        db=db,
        booking_code=payload.booking_code,
        provider_tx_id=payload.provider_tx_id,
        provider=payload.provider,
        amount_paid=payload.amount,
    )


@router.post("/simulate-webhook/{booking_code}", response_model=PaymentResponse)
async def simulate_webhook(
    booking_code: str,
    claims: dict | None = Depends(get_optional_claims),
    x_internal_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not settings.is_demo_webhook_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chế độ giả lập Webhook đang tắt")
    is_privileged = bool(claims and claims.get("role") in ("STAFF", "ADMIN"))
    if not (is_privileged or is_valid_internal_key(x_internal_key)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản STAFF/ADMIN hoặc test nội bộ mới được kích hoạt giả lập thanh toán",
        )
    tx_id = f"DEMO-{uuid.uuid4().hex[:8].upper()}"
    return await confirm_payment_idempotent(
        db=db,
        booking_code=booking_code,
        provider_tx_id=tx_id,
        provider="VIETQR_DEMO",
    )
