import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import (
    FinancialAuditLog,
    PaymentAttempt,
    PaymentTransaction,
    ReconciliationCase,
    RefundTransaction,
)
from app.schemas import (
    ApproveRefundRequest,
    CreatePaymentRequest,
    CreateRefundRequest,
    ExecuteRefundRequest,
    FinancialAuditLogResponse,
    PaymentAttemptResponse,
    PaymentResponse,
    PaymentWebhookRequest,
    ReconciliationCaseResponse,
    RefundCallbackRequest,
    RefundResponse,
    RejectRefundRequest,
    SimulatePaymentRequest,
    UpdateReconciliationRequest,
)
from app.security import (
    authorize_booking_access,
    get_optional_claims,
    is_valid_internal_key,
    require_roles,
    verify_internal_key,
)
from app.services.payment_service import (
    approve_refund,
    confirm_payment_idempotent,
    create_or_get_payment,
    create_refund_request,
    execute_refund,
    process_refund_callback,
    reject_refund,
    retry_failed_payment,
    simulate_payment_outcome,
    update_reconciliation_case,
    verify_refund_callback_signature,
    verify_webhook_signature,
)

router = APIRouter(prefix="/api/payments", tags=["Payments & Financial Lifecycle"])


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


@router.get("/booking/{booking_code}/attempts", response_model=list[PaymentAttemptResponse])
async def get_payment_attempts_by_booking(
    booking_code: str,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    await authorize_booking_access(booking_code, claims, x_guest_token)
    rows = (
        await db.scalars(
            select(PaymentAttempt)
            .where(PaymentAttempt.booking_code == booking_code.strip())
            .order_by(desc(PaymentAttempt.created_at))
        )
    ).all()
    return [PaymentAttemptResponse.model_validate(r) for r in rows]


@router.get("/booking/{booking_code}/refunds", response_model=list[RefundResponse])
async def get_refunds_by_booking(
    booking_code: str,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    await authorize_booking_access(booking_code, claims, x_guest_token)
    rows = (
        await db.scalars(
            select(RefundTransaction)
            .where(RefundTransaction.booking_code == booking_code.strip())
            .order_by(desc(RefundTransaction.created_at))
        )
    ).all()
    return [RefundResponse.model_validate(r) for r in rows]


@router.post("/booking/{booking_code}/retry", response_model=PaymentResponse)
async def retry_payment_endpoint(
    booking_code: str,
    claims: dict | None = Depends(get_optional_claims),
    x_guest_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    await authorize_booking_access(booking_code, claims, x_guest_token)
    actor = str((claims or {}).get("email") or "guest")
    return await retry_failed_payment(db, booking_code, actor=actor)


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
        outcome=payload.outcome,
        failure_reason=payload.failure_reason,
        initiated_by="signed_webhook",
    )


@router.post("/refunds/callback", response_model=RefundResponse)
async def refund_callback(
    payload: RefundCallbackRequest,
    x_webhook_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not verify_refund_callback_signature(
        payload.refund_code, payload.provider_refund_id, payload.outcome, x_webhook_signature
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chữ ký Callback hoàn tiền không hợp lệ")
    return await process_refund_callback(
        db,
        refund_code=payload.refund_code,
        provider_refund_id=payload.provider_refund_id,
        outcome=payload.outcome,
        failure_reason=payload.failure_reason,
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
    actor = str((claims or {}).get("email") or "internal-test")
    return await simulate_payment_outcome(
        db=db,
        booking_code=booking_code,
        outcome="SUCCEEDED",
        actor=actor,
    )


@router.post("/simulate/{booking_code}", response_model=PaymentResponse)
async def simulate_payment_scenario(
    booking_code: str,
    payload: SimulatePaymentRequest,
    claims: dict | None = Depends(get_optional_claims),
    x_internal_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not settings.is_demo_webhook_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chế độ giả lập thanh toán đang tắt")
    is_privileged = bool(claims and claims.get("role") in ("STAFF", "ADMIN"))
    if not (is_privileged or is_valid_internal_key(x_internal_key)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản STAFF/ADMIN hoặc test nội bộ mới được sử dụng trình giả lập thanh toán",
        )
    actor = str((claims or {}).get("email") or "internal-test")
    return await simulate_payment_outcome(
        db=db,
        booking_code=booking_code,
        outcome=payload.outcome,
        amount=payload.amount,
        provider_tx_id=payload.provider_tx_id,
        failure_reason=payload.failure_reason,
        actor=actor,
    )


@router.post("/internal/refunds", response_model=RefundResponse, status_code=status.HTTP_201_CREATED)
async def internal_create_refund(
    payload: CreateRefundRequest,
    _: None = Depends(verify_internal_key),
    db: AsyncSession = Depends(get_db),
):
    return await create_refund_request(
        db,
        booking_code=payload.booking_code,
        requested_amount=payload.requested_amount,
        policy_tier=payload.policy_tier,
        policy_percent=payload.policy_percent,
        reason=payload.reason,
        requested_by="court-booking-service",
        actor_role="SYSTEM",
        admin_override_reason=payload.admin_override_reason,
        auto_approve=payload.auto_approve,
    )


# ----------------- ADMIN FINANCIAL MANAGEMENT -----------------


@router.get("/admin/transactions", response_model=list[PaymentResponse])
async def admin_list_transactions(
    status_filter: str | None = Query(default=None, alias="status"),
    reconciliation_status: str | None = Query(default=None),
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PaymentTransaction).order_by(desc(PaymentTransaction.created_at)).limit(200)
    if status_filter:
        stmt = stmt.where(PaymentTransaction.status == status_filter.strip().upper())
    if reconciliation_status:
        stmt = stmt.where(PaymentTransaction.reconciliation_status == reconciliation_status.strip().upper())
    rows = (await db.scalars(stmt)).all()
    return [PaymentResponse.model_validate(r) for r in rows]


@router.get("/admin/reconciliation", response_model=list[ReconciliationCaseResponse])
async def admin_list_reconciliation_cases(
    status_filter: str | None = Query(default=None, alias="status"),
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ReconciliationCase).order_by(desc(ReconciliationCase.created_at)).limit(200)
    if status_filter:
        stmt = stmt.where(ReconciliationCase.status == status_filter.strip().upper())
    rows = (await db.scalars(stmt)).all()
    return [ReconciliationCaseResponse.model_validate(r) for r in rows]


@router.post("/admin/reconciliation/{case_id}", response_model=ReconciliationCaseResponse)
async def admin_update_reconciliation(
    case_id: uuid.UUID,
    payload: UpdateReconciliationRequest,
    claims: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await update_reconciliation_case(
        db,
        case_id=case_id,
        new_status=payload.status,
        resolution_action=payload.resolution_action,
        resolution_note=payload.resolution_note,
        actor_email=str(claims.get("email") or "admin"),
    )


@router.get("/admin/refunds", response_model=list[RefundResponse])
async def admin_list_refunds(
    status_filter: str | None = Query(default=None, alias="status"),
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RefundTransaction).order_by(desc(RefundTransaction.created_at)).limit(200)
    if status_filter:
        stmt = stmt.where(RefundTransaction.status == status_filter.strip().upper())
    rows = (await db.scalars(stmt)).all()
    return [RefundResponse.model_validate(r) for r in rows]


@router.post("/admin/refunds", response_model=RefundResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_refund(
    payload: CreateRefundRequest,
    claims: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    if payload.policy_tier == "ADMIN_EXCEPTION" and not (payload.admin_override_reason or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hoàn tiền ngoại lệ (ADMIN_EXCEPTION) bắt buộc phải nhập lý do ngoại lệ",
        )
    return await create_refund_request(
        db,
        booking_code=payload.booking_code,
        requested_amount=payload.requested_amount,
        policy_tier=payload.policy_tier,
        policy_percent=payload.policy_percent,
        reason=payload.reason,
        requested_by=str(claims.get("email") or "admin"),
        actor_role="ADMIN",
        admin_override_reason=payload.admin_override_reason,
        auto_approve=payload.auto_approve,
    )


@router.post("/admin/refunds/{refund_id}/approve", response_model=RefundResponse)
async def admin_approve_refund(
    refund_id: uuid.UUID,
    payload: ApproveRefundRequest,
    claims: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await approve_refund(
        db,
        refund_id=refund_id,
        admin_email=str(claims.get("email") or "admin"),
        approved_amount=payload.approved_amount,
        note=payload.note,
    )


@router.post("/admin/refunds/{refund_id}/reject", response_model=RefundResponse)
async def admin_reject_refund(
    refund_id: uuid.UUID,
    payload: RejectRefundRequest,
    claims: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await reject_refund(
        db,
        refund_id=refund_id,
        admin_email=str(claims.get("email") or "admin"),
        rejection_reason=payload.rejection_reason,
    )


@router.post("/admin/refunds/{refund_id}/execute", response_model=RefundResponse)
async def admin_execute_refund(
    refund_id: uuid.UUID,
    payload: ExecuteRefundRequest,
    claims: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await execute_refund(
        db,
        refund_id=refund_id,
        admin_email=str(claims.get("email") or "admin"),
        outcome=payload.outcome,
        failure_reason=payload.failure_reason,
    )


@router.get("/admin/audit-logs", response_model=list[FinancialAuditLogResponse])
async def admin_list_financial_audit_logs(
    booking_code: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FinancialAuditLog).order_by(desc(FinancialAuditLog.created_at)).limit(300)
    if booking_code:
        stmt = stmt.where(FinancialAuditLog.booking_code == booking_code.strip())
    if entity_type:
        stmt = stmt.where(FinancialAuditLog.entity_type == entity_type.strip().upper())
    rows = (await db.scalars(stmt)).all()
    return [FinancialAuditLogResponse.model_validate(r) for r in rows]
