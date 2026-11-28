# B00 — Version B Integration & Reliability Architecture

- **Version A (`main`):** `bfa1535f1e754bd654b174a23ceb08d4f1b1c8cc` (Original backend + UI01/UI02/UI03 redesign)
- **P01 Preservation (`upgrade/p01-reliability` / `soa-p01-checkpoint`):** `d8f7fa3a579c89133660014f37e68f95b67870eb`
- **Version B (`upgrade/soa-complete`):** Branched from `main` (`bfa1535`), cherry-picked P01 (`8fc2c16`) with `-x`, plus B00 compatibility & reliability refinements.

## 1. Frontend-to-Backend Compatibility Updates
- **`frontend/src/types/index.ts`:** Added `reconciliation_status?: 'NONE' | 'COMPENSATION_REQUIRED'` and `reconciliation_note?: string | null` to `PaymentTransaction`.
- **`frontend/src/pages/CheckoutPage.tsx`:**
  - Polls `GET /api/payments/booking/{bookingCode}` on `CANCELLED`/`EXPIRED` states as well as `PENDING_PAYMENT`/`PAID`.
  - Distinguishes `PENDING_PAYMENT` + `payment.status === 'SUCCEEDED'` (*"Đã nhận thanh toán — Đang chờ xác nhận đặt sân"*) from unpaid VietQR state.
  - Distinguishes `PAID` without `ticket` yet (*"Đặt sân đã xác nhận — Đang chuẩn bị vé QR"*).
  - Surfaces `COMPENSATION_REQUIRED` warning banner with `provider_tx_id` and `reconciliation_note` when payment was received for an expired/cancelled booking.

## 2. P01 Reliability Review & Corrections (`R01`–`R07`)
- **R01 (Terminal Outbox Recovery):** Added `list_failed_outbox_events()` and `requeue_failed_outbox_event(event_id)` + `python -m app.events.outbox list-failed | retry-failed` CLI in `court-booking-service`, `payment-service`, and `checkin-qr-service` (preserving original `event_id` for downstream `inbox_events` deduplication).
- **R02 (Legacy RabbitMQ Queue Migration):** `.v2` queues (`booking.payment_events.v2`, `payment.booking_events.v2`, `checkin.events.v2`) avoid `PRECONDITION_FAILED` on existing brokers. Before cutover on a live broker, drain any legacy messages from `booking.payment_events`, `payment.booking_events`, and `checkin.events` (and ensure no consumer remains bound to `payment.succeeded` on `checkin.events`).
- **R03 (Transactional Consumer Correctness):** `claim_inbox_event` + business update + `enqueue_outbox_event` commit atomically before `message.ack()`.
- **R04 (Notification Side Effects):** `notification-service` records `InboxEvent` + `NotificationLog(SENT)` only *after* `aiosmtplib.send()` succeeds; SMTP failures record `NotificationLog(FAILED)` and route to `pickleball.dlq` without blocking future retries.
- **R05 (Out-of-Order Events):** Added `CancelledBooking` (`cancelled_bookings` table) in `checkin-qr-service` so `booking.cancelled` arriving *before* `booking.confirmed` prevents premature or delayed ticket creation.
- **R06 (Compensation Integrity):** `booking_compensations` and `payment_compensations` retain `COMPENSATION_REQUIRED` evidence without auto-refunding.
- **R07 (Rollback Safety):** Updated `docs/verification/P01_ROLLBACK.md` to document additive schema compatibility and RabbitMQ `.v2` queue draining precautions.
