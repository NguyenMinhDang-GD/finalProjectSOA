# B00 — Remaining Risks & Deferred Items (B01–B06)

1. **Redis Lock Ownership & Multi-Replica Expiration Worker (B01):**
   - `release_booking_slots` still deletes Redis keys without Lua ownership verification, and `run_expiration_worker` does not yet use `FOR UPDATE SKIP LOCKED`.
2. **Security Hardening & Guest Access Tokens (B02):**
   - Public `lookup`, `cancel`, `payments`, and `ticket` endpoints still rely on `booking_code` without ownership/guest tokens; `booking_code` entropy is 16-bit/day; `ENABLE_DEMO_WEBHOOK=true` and `ALLOW_DEMO_BYPASS_TIME=true` remain enabled for dev/demo; CORS is `*`; no Nginx rate limiting.
3. **External Providers & Financial Operations (B03–B05):**
   - VietQR is a static URL template; no real payOS/SePay webhook, Brevo SMTP, Open-Meteo weather, or automated refund execution for `COMPENSATION_REQUIRED` records.
4. **Legacy RabbitMQ Queue Cutover:**
   - Upgrading an already-running broker with unconsumed messages in legacy queues requires draining those queues before cutover to `.v2`.
