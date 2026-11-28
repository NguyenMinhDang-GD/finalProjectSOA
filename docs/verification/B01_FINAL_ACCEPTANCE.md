# B01 Final Acceptance Report — Pickleball SOA Arena

## 1. Summary of B01-V Verification (V01–V08)
- **V01 (Inactive Account & Privileged Session Security — SEC-12)**: `auth-service` exposes `GET /api/auth/internal/users/{user_id}/status` (protected by `verify_internal_key` with `hmac.compare_digest`). `court-booking-service`, `payment-service`, and `checkin-qr-service` verify live `is_active` status synchronously with zero caching (fail-closed `503` if `auth-service` is unreachable; `403` if `is_active == False`).
- **V02 (Guest Token Lifecycle)**: `BookingOrder` stores `guest_token_hash` (SHA-256), `guest_token_expires_at` (`max(hold_expiry, play_end + 24h)`), and `guest_token_revoked_at`. `POST /api/bookings/admin/{code}/revoke-guest-token` allows immediate operator revocation. Cancelled/expired bookings retain read-only lookup access until token expiration/revocation; mutations are rejected. Legacy guest bookings (`guest_token_hash IS NULL`) are denied unauthenticated (`401`/`403`) and require `STAFF`/`ADMIN` assistance.
- **V03 (Production Demo Credential & Feature Isolation)**: `seed_default_users` in `auth-service` skips seeding `admin@pickleball.vn`, `staff@pickleball.vn`, and `khachhang@pickleball.vn` when `APP_ENV=production`. Demo webhook simulation and check-in time bypass are disabled in `production`.
- **V04 (Frontend Security Compatibility)**: `VITE_ENABLE_DEMO_CONTROLS=false` in `docker-compose.prod.yml` hides login demo autofill, staff time-bypass toggle, and checkout demo panel. In dev/test, checkout demo simulation is shown only to `STAFF`/`ADMIN`.
- **V05 (Isolated B00-to-B01 Migration)**: Verified upgrading `soa-b00-ui-release` (`15d8259`) to B01-V against the same isolated `pkb-b01-mig` volume: zero row loss across all tables, 4 additive columns verified, legacy registered lookup `200`, legacy guest lookup `401` unauth / `403` bogus token / `200` admin, and restart preservation verified.
- **V06 (Production-Like Runtime)**: Verified `docker-compose.prod.yml` (`pkb-prod-test`, port `18081`): Gateway is the sole exposed port, demo default accounts fail (`401`), `/api/bookings/internal/*` blocked (`403`), demo webhook disabled (`403`), and customer booking/payment/cancel flows succeed.
- **V07 (Financial State Races)**: Verified expiration vs payment, cancel vs payment, duplicate callbacks, and delayed callbacks preserve `EXPIRED`/`CANCELLED`, record `COMPENSATION_REQUIRED` without resurrection, and issue `0` tickets.
- **V08 (Payment Integration Readiness)**: Documented in `docs/implementation/B02_PAYMENT_READINESS.md`.

## 2. Remaining Limitations
- TLS/HTTPS termination is not configured on the local Nginx container (must be terminated at a reverse proxy/load balancer or tunnel in external deployments).
- Real payment provider integration (`payOS` / `SePay`) and automated refunds remain out of scope until `B02`.
- Physical webcam QR scanning was not executed in headless CI/verification environments.
