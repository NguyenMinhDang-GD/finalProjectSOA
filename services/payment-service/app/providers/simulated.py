"""Controlled Payment Provider Abstraction & Simulated Gateway (B02).

IMPORTANT: No real financial provider (payOS, SePay, Stripe, MoMo, ZaloPay)
and no real VietQR bank-transfer payloads are used anywhere in this module.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import uuid
from dataclasses import dataclass
from typing import Protocol


SIMULATION_NOTICE_VI = (
    "THANH TOÁN GIẢ LẬP — Chỉ dùng cho kiểm thử và trình diễn. "
    "Không phải mã chuyển khoản ngân hàng thật, không phát sinh giao dịch tiền thật."
)


@dataclass(frozen=True)
class CheckoutSessionResult:
    provider: str
    payment_mode: str
    reference_code: str
    qr_image_url: str
    bank_bin: str
    bank_account_no: str
    bank_account_name: str
    simulation_notice: str


@dataclass(frozen=True)
class RefundExecutionResult:
    provider: str
    provider_refund_id: str
    status: str  # SUCCEEDED | FAILED | PROCESSING
    message: str


class PaymentProvider(Protocol):
    name: str

    def create_checkout_session(
        self,
        *,
        booking_code: str,
        amount_vnd: int,
        payment_mode: str,
    ) -> CheckoutSessionResult: ...

    def verify_webhook_signature(
        self,
        *,
        booking_code: str,
        amount_vnd: int,
        provider_tx_id: str,
        signature: str | None,
        secret: str,
    ) -> bool: ...

    def execute_refund(
        self,
        *,
        refund_code: str,
        booking_code: str,
        amount_vnd: int,
        outcome: str = "SUCCEEDED",
    ) -> RefundExecutionResult: ...


def build_non_financial_demo_qr(booking_code: str, amount_vnd: int) -> str:
    """Generate a non-financial demonstration SVG QR badge (data URI).

    Contains NO bank BIN, NO bank account number, and NO VietQR URL.
    """
    seed = hashlib.sha256(f"SIMULATED-DEMO:{booking_code}:{amount_vnd}".encode("utf-8")).digest()
    grid_size = 15
    cell = 10
    pad = 18
    size = grid_size * cell + pad * 2

    rects: list[str] = []
    # Draw 3 finder-like corner squares + deterministic demo pattern
    def _is_finder(r: int, c: int) -> bool:
        in_tl = r < 4 and c < 4
        in_tr = r < 4 and c >= grid_size - 4
        in_bl = r >= grid_size - 4 and c < 4
        return in_tl or in_tr or in_bl

    for r in range(grid_size):
        for c in range(grid_size):
            if _is_finder(r, c):
                border = (
                    r in (0, 3) or c in (0, 3)
                    or (r in (0, 3) and c >= grid_size - 4)
                    or (c in (grid_size - 4, grid_size - 1) and r < 4)
                    or (r in (grid_size - 4, grid_size - 1) and c < 4)
                )
                center = (
                    (r in (1, 2) and c in (1, 2))
                    or (r in (1, 2) and c in (grid_size - 3, grid_size - 2))
                    or (r in (grid_size - 3, grid_size - 2) and c in (1, 2))
                )
                fill = "#0f172a" if (border or center) else "#ffffff"
            else:
                bit_idx = (r * grid_size + c) % (len(seed) * 8)
                byte_val = seed[bit_idx // 8]
                bit = (byte_val >> (bit_idx % 8)) & 1
                fill = "#0f172a" if bit else "#f8fafc"
            if fill != "#ffffff" and fill != "#f8fafc":
                rects.append(
                    f'<rect x="{pad + c * cell}" y="{pad + r * cell}" '
                    f'width="{cell}" height="{cell}" rx="2" fill="{fill}"/>'
                )

    safe_code = html.escape(booking_code, quote=True)
    amount_label = f"{amount_vnd:,} VND".replace(",", ".")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size + 46}" '
        f'viewBox="0 0 {size} {size + 46}">'
        f'<rect width="{size}" height="{size + 46}" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>'
        f'<rect x="10" y="8" width="{size - 20}" height="22" rx="6" fill="#fef3c7" stroke="#f59e0b" stroke-width="1"/>'
        f'<text x="{size // 2}" y="23" text-anchor="middle" font-family="Arial,sans-serif" '
        f'font-size="10" font-weight="700" fill="#92400e">THANH TOAN GIA LAP (DEMO)</text>'
        f'<g transform="translate(0, 20)">{"".join(rects)}</g>'
        f'<text x="{size // 2}" y="{size + 22}" text-anchor="middle" font-family="monospace" '
        f'font-size="11" font-weight="700" fill="#0f172a">{safe_code}</text>'
        f'<text x="{size // 2}" y="{size + 38}" text-anchor="middle" font-family="Arial,sans-serif" '
        f'font-size="11" font-weight="700" fill="#047857">{amount_label}</text>'
        f"</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


class SimulatedPaymentProvider:
    """Controlled simulated payment provider (MOCK_DEMO / MOCK_TEST)."""

    name = "SIMULATED_GATEWAY"

    def create_checkout_session(
        self,
        *,
        booking_code: str,
        amount_vnd: int,
        payment_mode: str,
    ) -> CheckoutSessionResult:
        return CheckoutSessionResult(
            provider=self.name,
            payment_mode=payment_mode,
            reference_code=f"SIM-{booking_code}",
            qr_image_url=build_non_financial_demo_qr(booking_code, amount_vnd),
            bank_bin="SIMULATED",
            bank_account_no="DEMO-ONLY",
            bank_account_name="THANH TOÁN GIẢ LẬP",
            simulation_notice=SIMULATION_NOTICE_VI,
        )

    def verify_webhook_signature(
        self,
        *,
        booking_code: str,
        amount_vnd: int,
        provider_tx_id: str,
        signature: str | None,
        secret: str,
    ) -> bool:
        if not secret or not signature:
            return False
        canonical = f"{booking_code}:{amount_vnd}:{provider_tx_id}"
        expected = hmac.new(
            secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip().lower())

    def execute_refund(
        self,
        *,
        refund_code: str,
        booking_code: str,
        amount_vnd: int,
        outcome: str = "SUCCEEDED",
    ) -> RefundExecutionResult:
        normalized = outcome.strip().upper()
        provider_refund_id = f"SIMRF-{refund_code}-{uuid.uuid4().hex[:6].upper()}"
        if normalized == "FAILED":
            return RefundExecutionResult(
                provider=self.name,
                provider_refund_id=provider_refund_id,
                status="FAILED",
                message=f"Simulated refund failure for {booking_code} ({amount_vnd:,} VND)",
            )
        if normalized == "PROCESSING":
            return RefundExecutionResult(
                provider=self.name,
                provider_refund_id=provider_refund_id,
                status="PROCESSING",
                message=f"Simulated refund processing asynchronously for {booking_code}",
            )
        return RefundExecutionResult(
            provider=self.name,
            provider_refund_id=provider_refund_id,
            status="SUCCEEDED",
            message=f"Simulated refund completed for {booking_code} ({amount_vnd:,} VND)",
        )


def get_payment_provider(payment_mode: str) -> SimulatedPaymentProvider | None:
    if payment_mode in ("MOCK_DEMO", "MOCK_TEST"):
        return SimulatedPaymentProvider()
    return None
