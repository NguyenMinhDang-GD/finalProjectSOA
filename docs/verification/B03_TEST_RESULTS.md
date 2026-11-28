# B03 — Verification & Regression Test Results

## 1. Automated Verification Runner (`scripts/verify-b03.ps1`)
Executed on isolated `pkb-test` (`docker-compose.test.yml`, port `18080`, torn down with `down -v --remove-orphans`).

| Suite | Scope | Result |
|---|---|---|
| `npm run build` | TypeScript (`tsc`) + Vite production bundle | PASS (exit 0) |
| `docker compose config` | Default, test, and prod compose syntax | PASS (exit 0) |
| `tests/test_p01_reliability.py` | Outbox, Inbox, DLQ, RabbitMQ resilience | PASS (exit 0) |
| `tests/test_b01_concurrency_security.py` | Redis/Postgres locks, RBAC, Guest token, Internal Auth | PASS (exit 0) |
| `tests/test_b02_financial_lifecycle.py` | Simulated payment, attempts, refunds, reconciliation | PASS (exit 0) |
| `tests/test_b02_v_acceptance.py` | V01–V06 distributed race, cumulative accounting, outage | PASS (exit 0) |
| `tests/test_b03_business_operations.py` | **46 assertions**: `R01`–`R16`, `W01`–`W10`, `M01`–`M09`, `O01`–`O11` | **PASS (46/46, 0 failed)** |

## 2. Playwright E2E UI Verification (`verify_b03_ui.mjs`)
Executed against isolated `pkb-test` at `http://localhost:18080`:
- Customer Checkout Paid + Inline Rescheduling (`Đổi lịch chơi` -> slot selection -> `v2` revision): **PASS**
- Admin Maintenance Scheduling (`Bảo trì sân` -> `SCHEDULED`) & Operational Audit (`MAINTENANCE_SCHEDULED`): **PASS**
- Staff Walk-in Booking + Immediate Simulated Counter Cash Collection (`Đã tạo đơn Walk-in`): **PASS**
- Mobile `390x844` responsive check on `/staff/scanner` (`Vận hành đơn`): **PASS (0 horizontal overflow)**
- Browser console/page errors: **0**

Evidence screenshots saved under `b00-ui-evidence/b03/`:
- `b03-checkout-rescheduled.png`
- `b03-admin-maintenance.png`
- `b03-admin-op-audit.png`
- `b03-staff-operations.png`
- `b03-mobile-staff.png`
