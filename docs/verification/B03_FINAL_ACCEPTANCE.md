# B03 — Final Acceptance & Release Verification (`B03-V-PUBLISH`)

## 1. V01–V08 Acceptance Summary

| Check | Scope | Result & Evidence |
|---|---|---|
| **V01** | Rescheduling & Payment Revision Sync Durability | **PASS** — Added Outbox/Inbox `booking.rescheduled` consumer in `payment-service` (`payment.booking_events.v2`) + strict monotonic `tx.booking_revision >= booking_revision` guard in `sync_payment_revision`, plus `"booking_revision"` in `booking.confirmed` payload. Verified in `test_b03_v_acceptance.py`: unpaid reschedule while `payment-service` stopped durably converged to `150000:2` after restart and rejected stale `v1` sync (`updated=False, stale=True`). |
| **V02** | Booking Revision & Payment Callback Integrity | **PASS** — Verified in `test_b03_business_operations.py` (`R02`, `R03`, `R07`) and `test_b02_v_acceptance.py` (`V02`, `V03-V04`): stale callbacks cannot confirm incompatible obligations, cumulative receipts remain traceable, and paid same-price rescheduling preserves financial evidence. |
| **V03** | Ticket Versioning & Event Ordering | **PASS** — `checkin-qr-service` binds `booking.confirmed`, `booking.cancelled`, `booking.rescheduled`, `booking.no_show`, `booking.completed`. Verified in `test_b03_v_acceptance.py`: paid reschedule while `checkin-qr-service` stopped durably converged ticket `v2 -> v3`, rejected old `v2` QR (`400`), and admitted `v3` QR (`200`). |
| **V04** | Notification Idempotency & Index Migration | **PASS** — Legacy `uq_notification_sent_booking` dropped cleanly (`DROP INDEX IF EXISTS`). Per-event idempotency enforced via `InboxEvent` (`consumer_name`, `event_id`). Residual limitation: SMTP Mailpit send and DB `NotificationLog` commit are not a distributed 2PC transaction, so a crash between SMTP send and DB commit could re-send on RabbitMQ redelivery (at-least-once email delivery). |
| **V05** | Maintenance & Operational Concurrency | **PASS** — Verified in `test_b03_business_operations.py` (`M05`, `M06`, `O03`, `O04`, `O08`): `Court` `SELECT ... FOR UPDATE` serializes booking, walk-in, reschedule, and maintenance even with Redis stopped; `BookingOrder` `FOR UPDATE` serializes No-Show vs Check-in and Completion. |
| **V06** | Migration & Restart Evidence | **PASS** — Verified in `run_b03_migration.py` (`soa-b02-checkpoint` → B03): row counts preserved (`bookings`, `payments`), B03 columns backfilled (`ONLINE:1`, `SIMULATED_ONLINE:1`), 3 new tables created, and repeatable service restarts succeeded (`B03_MIGRATION_AND_RESTART_OK`). |
| **V07** | PlantUML Validation Tooling | **PASS** — Validated and rendered all 15 `.puml` files (39 diagram blocks) using official PlantUML `v1.2024.8` + Java `26.0.2.1` + Graphviz `2.44.1`: `CHECKONLY_EXIT=0`, `RENDER_EXIT=0`, **39/39 SVGs rendered**, **0 failed**. |
| **V08** | Diagram Semantic Accuracy | **PASS** — Updated `SEQ_OPERATIONS_B03.puml` and traceability docs to match final V01/V03 Outbox/Inbox durability. |

## 2. Regression Suite Results (`scripts/verify-b03.ps1`)
- `npm run build` (`tsc && vite build`): **PASS** (exit 0)
- `docker compose config --quiet` (default, test, prod): **PASS** (exit 0)
- `tests/test_p01_reliability.py`: **PASS**
- `tests/test_b01_concurrency_security.py`: **PASS**
- `tests/test_b02_financial_lifecycle.py`: **PASS** (10/10 groups)
- `tests/test_b02_v_acceptance.py`: **PASS** (`V01`–`V06`)
- `tests/test_b03_business_operations.py`: **PASS** (46/46 assertions)
- `tests/test_b03_v_acceptance.py`: **PASS** (`V01`, `V03`)

## 3. Residual Limitations & Non-Commercial Scope
- Payment and counter cash collection remain `MOCK_DEMO` / `SIMULATED_COUNTER` only (no real bank or payment gateway).
- Notification delivery uses local Mailpit SMTP only (Brevo deferred to B04); email delivery is at-least-once across crash windows between SMTP send and DB commit.
- Physical webcam QR scanning remains `NOT RUN` in headless CI; manual QR payload and staff scanner UI flows are verified.

## 4. Reproduction Commands
```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-b03.ps1
git diff --check
docker compose config --quiet
```
