import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import PaymentTransaction
from app.schemas import CreatePaymentRequest, PaymentResponse, PaymentWebhookRequest
from app.services.payment_service import (
    confirm_payment_idempotent,
    create_or_get_payment,
    verify_webhook_signature,
)

router = APIRouter(prefix="/api/payments", tags=["Payments & VietQR"])


@router.post("/create", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(payload: CreatePaymentRequest, db: AsyncSession = Depends(get_db)):
    return await create_or_get_payment(db, payload.booking_code)


@router.get("/booking/{booking_code}", response_model=PaymentResponse)
async def get_payment_by_booking(booking_code: str, db: AsyncSession = Depends(get_db)):
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
async def simulate_webhook(booking_code: str, db: AsyncSession = Depends(get_db)):
    if not settings.enable_demo_webhook:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chế độ giả lập Webhook đang tắt")
    tx_id = f"DEMO-{uuid.uuid4().hex[:8].upper()}"
    return await confirm_payment_idempotent(
        db=db,
        booking_code=booking_code,
        provider_tx_id=tx_id,
        provider="VIETQR_DEMO",
    )
