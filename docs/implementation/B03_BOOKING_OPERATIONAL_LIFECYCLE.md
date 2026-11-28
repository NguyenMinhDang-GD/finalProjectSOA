# B03 — Booking Operational Lifecycle (Check-in, No-Show, Completion)

## 1. Admission & Check-in Tracking
- `BookingOrder.admission_status` (`NONE` -> `ADMITTED`), `checked_in_at`, `checked_in_by`.
- `POST /api/bookings/internal/claim-checkin` enforces `expected_revision == order.booking_revision` and blocks `CANCELLED`, `EXPIRED`, `NO_SHOW`, or `COMPLETED` bookings, recording `BOOKING_ADMITTED` in `OperationalAuditLog`.

## 2. No-Show Policy (`POST /api/bookings/staff/{code}/no-show`)
- Restricted to `STAFF`/`ADMIN`.
- Acquires `BookingOrder` `SELECT ... FOR UPDATE` lock so concurrent Check-in Scan vs No-Show cannot produce a split-brain `NO_SHOW + ADMITTED` state.
- Blocks if `admission_status == "ADMITTED"` (`409`) or `status != "PAID"`.
- Enforces `now_vn >= slot_start_vn + grace_minutes` (`no_show_grace_minutes = 30`, overridable via `grace_minutes_override`).
- Transitions `status` -> `NO_SHOW`, records `OperationalAuditLog(action="BOOKING_NO_SHOW")`, and enqueues Outbox `booking.no_show`.

## 3. Completion Policy (`POST /api/bookings/staff/{code}/complete`)
- Restricted to `STAFF`/`ADMIN`.
- Idempotent if already `COMPLETED`.
- Requires `status == "PAID"` and `admission_status == "ADMITTED"`.
- Requires `now_vn >= slot_end_vn`, unless `early_completion=True` and `len(reason.strip()) >= 5`.
- Transitions `status` -> `COMPLETED`, records `OperationalAuditLog(action="BOOKING_COMPLETED")`, and enqueues Outbox `booking.completed`.
