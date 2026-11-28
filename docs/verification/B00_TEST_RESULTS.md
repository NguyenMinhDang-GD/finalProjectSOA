# B00 — Integrated Acceptance Test Results

**Environment:** Isolated `pkb-test` (`docker-compose.test.yml`) running Version B backend + redesigned frontend (`http://localhost:18080`).

## 1. P01 Regression (`T01`–`T15`)
- **T01–T14** (`python tests/test_p01_reliability.py`, exit code `0`): **ALL PASS** (`PKB-20261130-E3CC`, `F60C`, `413D`, `3B7A`, `CAF4`, `1374`, `C1E9`, DLQ `0 -> 3`, concurrent `SKIP LOCKED` `10/10`).
- **T15** (`docker compose config --quiet`, `docker build ./frontend`, `docker compose ps`): **PASS**.

## 2. B00 Acceptance Tests (`B00-T01`–`B00-T12`)

| Test | Status | Evidence |
| :--- | :---: | :--- |
| **B00-T01** (Branch isolation) | **PASS** | `main` at `bfa1535`, `soa-p01-checkpoint` at `d8f7fa3`, work on `upgrade/soa-complete` (`8fc2c16`), 0 pushes |
| **B00-T02** (UI preservation) | **PASS** | Complete UI01/UI02/UI03 frontend preserved + async state compatibility in `CheckoutPage.tsx` |
| **B00-T03** (Integrated browser happy path) | **PASS** | Booked `PKB-20261203-9AE5` -> simulated payment -> `PAID` -> QR ticket -> Mailpit email -> Staff check-in `HỢP LỆ` |
| **B00-T04** (Async payment-to-ticket progression) | **PASS** | Held `lookup` as `PENDING_PAYMENT` -> UI showed `Đã nhận thanh toán — Đang chờ xác nhận đặt sân` -> transitioned to QR ticket |
| **B00-T05** (Invalid booking with received payment) | **PASS** | Expired `PKB-20261203-D5F9` + signed webhook -> UI showed `Cần đối soát / hoàn tiền` (`COMPENSATION_REQUIRED`), `0` tickets |
| **B00-T06** (Failed outbox recovery) | **PASS** | `list-failed` & `retry-failed --event-id afddec30-...` reset `FAILED -> PENDING -> PUBLISHED` preserving `event_id` |
| **B00-T07** (Cancellation before ticket issuance) | **PASS** | Out-of-order `booking.cancelled` before `booking.confirmed` created `0` tickets (`CancelledBooking` guard) |
| **B00-T08** (Existing DB upgrade) | **PASS** | Isolated `pkb-mig-test`: `main` -> Version B preserved all legacy rows (`users=3, bookings=2, payments=2, tickets=1, emails=1`) |
| **B00-T09** (Migration restart) | **PASS** | Restarting upgraded `pkb-mig-test` services preserved all records (`bookings=2`) |
| **B00-T10** (Frontend production build) | **PASS** | `docker build ./frontend` (`tsc && vite build`) succeeded with route code splitting |
| **B00-T11** (Responsive UI regression) | **PASS** | `390x844` & `1280x800` across `/`, `/checkout/:code`, `/staff/scanner`, `/admin`: `0` overflows, `0` page errors |
| **B00-T12** (Protected main runtime) | **PASS** | Main stack containers untouched (`Up 40+ min`), zero main DB/volume mutations |
