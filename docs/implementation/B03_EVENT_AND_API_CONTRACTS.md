# B03 — Event & API Contracts

## 1. New & Updated HTTP Endpoints

### `court-booking-service`
- `POST /api/bookings/{booking_code}/reschedule-quote` (Customer/Guest token/Staff/Admin): `{ court_id, play_date, hours }` -> `{ eligible, reason, current_amount, new_amount, same_price, hours_until_current_start }`
- `POST /api/bookings/{booking_code}/reschedule` (Customer/Guest token/Staff/Admin): `{ court_id, play_date, hours, idempotency_key?, expected_revision?, reason?, staff_override? }` -> `BookingResponse`
- `GET /api/bookings/{booking_code}/reschedule-history` -> `RescheduleHistoryResponse[]`
- `POST /api/bookings/staff/walk-in` (`STAFF`/`ADMIN`): `{ court_id, play_date, hours, customer_name, customer_phone, customer_email? }` -> `BookingResponse`
- `POST /api/bookings/staff/{booking_code}/no-show` (`STAFF`/`ADMIN`): `{ reason, grace_minutes_override? }` -> `BookingResponse`
- `POST /api/bookings/staff/{booking_code}/complete` (`STAFF`/`ADMIN`): `{ reason, early_completion? }` -> `BookingResponse`
- `GET /api/bookings/maintenance?play_date=...` -> `MaintenanceBlockResponse[]`
- `POST /api/bookings/admin/maintenance` (`ADMIN`): `{ court_id, play_date, start_hour, end_hour, reason, idempotency_key? }` -> `MaintenanceBlockResponse`
- `POST /api/bookings/admin/maintenance/{id}/cancel` (`ADMIN`) -> `MaintenanceBlockResponse`
- `GET /api/bookings/admin/operational-audit?entity_id=...` (`ADMIN`) -> `OperationalAuditLogResponse[]`

### `payment-service`
- `POST /api/payments/staff/cash-collect` (`STAFF`/`ADMIN`): `{ booking_code, amount, idempotency_key, note? }` -> `PaymentResponse` (`payment_method="SIMULATED_CASH"`, `provider="SIMULATED_COUNTER"`)
- `POST /api/payments/internal/{booking_code}/sync-revision` (Internal Service Token)
- `GET /api/payments/internal/{booking_code}/reschedule-check` (Internal Service Token)

## 2. Outbox / RabbitMQ Events (`pickleball.events` topic exchange)
- `booking.rescheduled` -> consumed by `checkin-qr-service` (updates `booking_revision`, generates `r{rev}` QR) & `notification-service` (sends reschedule email).
- `booking.no_show` -> consumed by `notification-service` (sends No-Show email).
- `booking.completed` -> consumed by `notification-service` (sends completion email).
- `court.maintenance_scheduled` / `court.maintenance_cancelled` -> published via Outbox for observability/audit.
