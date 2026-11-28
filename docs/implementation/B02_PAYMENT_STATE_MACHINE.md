# B02 Payment State Machine & Exact VND Integrity

## 1. Payment States (`payment_transactions.status`)

- `PENDING`: Checkout session created; awaiting simulated payment.
- `PROCESSING`: Asynchronous payment in progress.
- `SUCCEEDED`: Full expected VND amount received (`received_amount >= expected_amount`); emits `payment.succeeded` via Outbox.
- `FAILED`: Provider decline or underpayment (`received_amount < expected_amount`); booking remains `PENDING_PAYMENT` and customer can retry via `POST /api/payments/booking/{booking_code}/retry`.
- `CANCELLED` / `EXPIRED`: Booking was cancelled or expired before payment confirmation.

## 2. Exact Integer VND Handling

- `validate_exact_vnd()` in `services/payment-service/app/schemas.py` rejects fractional VND values (HTTP 422).
- `expected_amount`, `received_amount`, and `refunded_amount` are stored as integer VND columns alongside legacy `amount` (`Numeric(12, 2)`).

## 3. Attempt Tracking

Every simulated outcome (`PROCESSING`, `SUCCEEDED`, `FAILED`, `UNDERPAID`, `OVERPAID`, `DUPLICATE`, `LATE`) is recorded in `payment_attempts` with `attempt_number`, `provider_tx_id`, `expected_amount`, `received_amount`, `failure_reason`, and `initiated_by`.
