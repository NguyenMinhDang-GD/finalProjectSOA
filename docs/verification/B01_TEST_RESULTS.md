# B01 Test Results

## 1. Concurrency Suite (`tests/test_b01_concurrency_security.py`)
Executed against isolated `pkb-test` (`http://localhost:18080`):
- **C01**: `PASS` — 50 concurrent single-slot requests -> `1×201`, `49×409`, `0×500`, `active_slots=1`.
- **C02**: `PASS` — Multi-slot atomic rollback left `0` partial slots.
- **C03**: `PASS` — Lua compare-and-delete preserved new owner's lock against stale token.
- **C04**: `PASS` — Partial acquisition failure released only caller-owned lock keys.
- **C05**: `PASS` — Redis outage fell back to PostgreSQL `uq_active_court_slot` (`201` then `409`).
- **C06**: `PASS` — Concurrent `SKIP LOCKED` expiration workers expired 2 due bookings once each.
- **C07**: `PASS` — Expiration vs payment preserved `EXPIRED` + `COMPENSATION_REQUIRED`, `0` tickets.
- **C08**: `PASS` — Cancel vs payment race settled deterministically (`CANCELLED`, `0` tickets).
- **C09**: `PASS` — Existing booking kept snapshot amount `150000.0` after pricing rule edit.

## 2. Security Suite (`tests/test_b01_concurrency_security.py`)
- **S01–S05**: `PASS` — Customer ownership (`403`), unauthorized cancel (`401`/`403`), guest token (`200`/`401`/`403`), payment ownership (`401`/`403`), QR ticket ownership (`200`/`401`/`403`).
- **S06–S09**: `PASS` — RBAC (`403`), registration forced `role=CUSTOMER`, invalid JWT (`401`), inactive account (`403` on login & `/me`).
- **S10–S14**: `PASS` — Prod disables demo webhook & time bypass, `simulate-webhook` blocks `CUSTOMER` (`403`) & allows `STAFF` (`200`), invalid webhook HMAC (`401`), internal endpoints blocked at Gateway & direct without key (`403`).
- **S15–S20**: `PASS` — Rate limiting (`429` on login burst; 15/15 `200` on normal polling), CORS policy, `docker-compose.prod.yml` exposes Gateway only, prod rejects default/short secrets, email HTML escaping (`&lt;script&gt;`), and no raw secrets in logs.

## 3. P01 Reliability Regression (`tests/test_p01_reliability.py`)
- **T01–T14**: `PASS` (adapted guest calls to pass `X-Guest-Token`; all original reliability assertions preserved).

## 4. Frontend E2E Regression (`verify_b01_ui.mjs`)
- **Result**: `B01_E2E_UI_PASS` (`guest=PKB-20261202-4C07E41FD2`, `reg=PKB-20261203-75B71171BD`) — guest checkout recovery, unauthorized lookup feedback, registered booking, staff demo payment + check-in + duplicate rejection, admin dashboard, and mobile `390×844` rendering.
