# B02 Deterministic Cancellation Policy & Refund Lifecycle

## 1. Deterministic Cancellation Policy (`court-booking-service`)

Evaluated in `Asia/Ho_Chi_Minh` timezone against `play_date` + `start_hour`:
- `PENDING_PAYMENT`: `UNPAID_RELEASE` (0% refund, immediate slot release).
- `PAID` with `CHECKED_IN` ticket: `CHECKED_IN_INELIGIBLE` (HTTP 409 Conflict — cancellation blocked).
- `PAID` with `hours_until_play >= 24.0`: `FULL_24H` (100% refund).
- `PAID` with `2.0 <= hours_until_play < 24.0`: `PARTIAL_2H_24H` (50% refund).
- `PAID` with `hours_until_play < 2.0`: `NON_REFUNDABLE_LT_2H` (0% automatic refund).
- Admin Exception (`POST /api/bookings/admin/{booking_code}/cancel` with `admin_exception=true`): `ADMIN_EXCEPTION`, requires mandatory `reason` (>= 3 chars) and optional `override_refund_percent` (0–100).

## 2. Check-in vs Cancellation Race Guard

During `scan_and_checkin()` in `checkin-qr-service`, the service performs an authoritative check against `GET /api/bookings/internal/{booking_code}` before marking any ticket `CHECKED_IN`. If the booking is `CANCELLED` or `EXPIRED`, check-in fails closed and revokes the local ticket immediately.

## 3. Refund State Machine (`refund_transactions`)

- `REQUESTED` -> `APPROVED` -> `PROCESSING` -> `SUCCEEDED` | `FAILED`
- `FAILED` -> retry via `POST /api/payments/admin/refunds/{id}/execute` (`retry_count` incremented)
- `REQUESTED` / `APPROVED` -> `REJECTED` (mandatory `rejection_reason`)
- Async callback: `POST /api/payments/refunds/callback` (HMAC-SHA256 verified)
- Over-refund protection: `create_refund_request`, `approve_refund`, and `execute_refund` lock `PaymentTransaction` with `SELECT ... FOR UPDATE` and enforce `sum(active/succeeded refunds) <= received_amount` (HTTP 409 on excess).
