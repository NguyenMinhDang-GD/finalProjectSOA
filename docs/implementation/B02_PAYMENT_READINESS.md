# B02 Payment Integration Readiness Assessment

## 1. Current Payment Service Contracts (`services/payment-service`)
- **Payment Creation (`POST /api/payments/create`)**: Requires booking ownership (`JWT` or `X-Guest-Token` verified via `court-booking-service`'s `POST /api/bookings/internal/{code}/authorize`). Idempotent per `booking_code`.
- **Authoritative Amount & Currency**: Derived strictly from `BookingOrder.total_amount` (VND, `Numeric(12, 2)`), snapshotted at reservation time. Client-supplied amounts are never trusted for payment creation.
- **Transaction Identifiers**: Internal `PaymentTransaction.id` (`UUID`), `booking_code` (`PKB-YYYYMMDD-XXXXXXXXXX`), and unique `provider_tx_id` (`uq_payment_provider_tx_id` partial unique index).
- **State Model**: `PENDING` -> `SUCCEEDED` | `EXPIRED` | `CANCELLED`, with `reconciliation_status` (`NONE` | `COMPENSATION_REQUIRED`) and `reconciliation_note`.
- **Callback Verification (`POST /api/payments/webhook`)**: Constant-time HMAC-SHA256 verification (`X-Webhook-Signature` over `{booking_code}:{int(round(amount))}:{provider_tx_id}`), fail-closed when `WEBHOOK_SECRET` is missing.
- **Outbox & Compensation**: `payment.succeeded` is persisted atomically in `outbox_events` (`SKIP LOCKED` dispatcher). Late/post-cancel/post-expiry payments are recorded in `payment_compensations` (`COMPENSATION_REQUIRED`) without resurrecting the booking or issuing a QR ticket.

## 2. Readiness for B02 (`payOS` / `SePay`)
**READY** — B01-V has eliminated unauthenticated payment creation/lookup, unauthorized demo simulation, weak booking codes, unsafe Redis lock releases, and inactive-account token reuse. B02 can now safely add an external provider adapter behind `payment-service` while preserving existing Saga choreography and compensation guarantees.
