# B03 — Walk-in Booking & Simulated Cash Collection

## 1. Walk-in Booking Policy
- Endpoint: `POST /api/bookings/staff/walk-in` (restricted to `STAFF` and `ADMIN`).
- Sets `booking_source = "WALK_IN"` and `OperationalAuditLog(action="WALK_IN_BOOKING_CREATED")`.
- **Current-Hour Policy**: Unlike advance online rules requiring future start hours, walk-in allows booking the current VN hour as long as `slot_end_vn > now_vn`. Past hours (`slot_end_vn <= now_vn`) are still rejected (`400`).
- Respects all `MaintenanceBlock` and `BookingSlot` uniqueness/locking constraints.

## 2. Simulated Cash Collection at Counter
- Endpoint: `POST /api/payments/staff/cash-collect` (restricted to `STAFF` and `ADMIN`).
- Validates `booking["status"] == "PENDING_PAYMENT"` and exact counter amount match (`amount == expected_amount`).
- Uses `idempotency_key` (`CASH-{idempotency_key}`) so duplicate counter clicks return the existing `PaymentTransaction` without double-counting.
- Sets `payment_method = "SIMULATED_CASH"`, `provider = "SIMULATED_COUNTER"`, `collected_by`, `collected_at`, and confirms the booking through the standard Outbox `payment.succeeded` pipeline.
- **No Real Money**: Explicitly operates in `SIMULATED` mode with no external bank, VietQR transfer, or gateway integration.
