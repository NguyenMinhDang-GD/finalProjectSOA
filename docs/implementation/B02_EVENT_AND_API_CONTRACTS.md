# B02 Event & API Contracts

## 1. New/Updated HTTP Endpoints

### `court-booking-service`
- `GET /api/bookings/{booking_code}/cancellation-quote` (owner/guest/staff/admin)
- `POST /api/bookings/{booking_code}/cancel` (supports `PENDING_PAYMENT` and eligible `PAID` bookings)
- `POST /api/bookings/admin/{booking_code}/cancel` (supports `admin_exception` & `override_refund_percent`)

### `checkin-qr-service`
- `GET /api/checkin/internal/ticket/{booking_code}` (`X-Internal-Key`)

### `payment-service`
- `GET /api/payments/booking/{booking_code}/attempts`
- `GET /api/payments/booking/{booking_code}/refunds`
- `POST /api/payments/booking/{booking_code}/retry`
- `POST /api/payments/simulate/{booking_code}` (`STAFF`/`ADMIN`/internal key, non-prod only)
- `POST /api/payments/refunds/callback` (`X-Webhook-Signature`)
- `POST /api/payments/internal/refunds` (`X-Internal-Key`)
- `GET /api/payments/admin/transactions` (`ADMIN`)
- `GET /api/payments/admin/reconciliation` & `POST /api/payments/admin/reconciliation/{case_id}` (`ADMIN`)
- `GET /api/payments/admin/refunds`, `POST /api/payments/admin/refunds`, `POST /api/payments/admin/refunds/{id}/approve|reject|execute` (`ADMIN`)
- `GET /api/payments/admin/audit-logs` (`ADMIN`)

## 2. Outbox / RabbitMQ Events

- `payment.succeeded`, `payment.failed`, `payment.reconciliation_required`, `payment.compensation_required`
- `refund.requested`, `refund.succeeded`, `refund.failed`
- `booking.cancelled` (extended with `policy_tier`, `policy_percent`, `refund_amount_vnd`, `cancelled_by`)
