# B02 Payment Simulation Architecture

## 1. Scope & Non-Real-Money Boundary

Real financial provider integrations (payOS, SePay, Stripe, MoMo, ZaloPay) and live VietQR bank-transfer QR generation are **explicitly excluded** from this project.

- Provider interface: `PaymentProvider` protocol in `services/payment-service/app/providers/simulated.py`
- Active implementation: `SimulatedPaymentProvider` (`provider="SIMULATED_GATEWAY"`)
- Demonstration QR: `build_non_financial_demo_qr()` generates an inline SVG data URI (`data:image/svg+xml;base64,...`) labeled `THANH TOAN GIA LAP (DEMO)` with `bank_bin="SIMULATED"`, `bank_account_no="DEMO-ONLY"`, and `bank_account_name="THANH TOÁN GIẢ LẬP"`.
- Check-in QR (`CheckinTicket` in `checkin-qr-service`) remains a genuine HMAC-signed ticket (`PKB1.<ticket_id>.<booking_code>.<sig>`).

## 2. Runtime Modes

Configured via `PAYMENT_MODE` in `services/payment-service/app/config.py`:
- `MOCK_DEMO` (default in `docker-compose.yml`): interactive simulation controls enabled for `STAFF`/`ADMIN` (when `APP_ENV != production` and `ENABLE_DEMO_WEBHOOK=true`).
- `MOCK_TEST` (used in `docker-compose.test.yml`): automated test simulation enabled.
- `DISABLED`: payment creation, webhook confirmation, retry, and refund execution return `503 Service Unavailable`.
- Production guard: `is_demo_webhook_enabled` returns `False` whenever `APP_ENV=production` or `ENABLE_DEMO_WEBHOOK=false`.
