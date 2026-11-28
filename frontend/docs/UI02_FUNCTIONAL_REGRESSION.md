# UI02 — Functional Regression Report

Executed via Playwright against isolated `pkb-ui02-test` (`http://localhost:18080`, original `main` backend + UI01/UI02 frontend).

| Area | Test IDs | Status | Evidence |
| :--- | :--- | :---: | :--- |
| **Customer Booking** | `C01`–`C07` | **PASS** | Availability load, branch/location reset, date reload, contiguous 1–6h guard, price summary, guest & registered booking |
| **Customer Edge** | `C08`–`C10` | **PASS (Static + Negative)** | Conflict reload, `extractApiErrorMessage` for FastAPI 422, `submitting` disabled button guard |
| **Authentication** | `A01`–`A07` | **PASS** | Role-based login, invalid login `401` alert, registration, session reload, logout, route guards, password toggle |
| **Checkout & Payment** | `P01`, `P02`, `P04`–`P07`, `P09`, `P10` | **PASS** | 1x `POST /create`, read-only `GET /booking` polling, reload recovery, transient abort handling, demo webhook -> `PAID`, cancel dialog, QR image & PNG download (`ve-qr-*.png`) |
| **Polling Cleanup & Print** | `P03`, `P10 (print)` | **PASS (Code + Browser)** | `clearInterval` on unmount/terminal state; `window.print()` wired with `@media print` |
| **Lookup & 404** | `LOOKUP_404` | **PASS** | Valid booking lookup + `404` `NotFoundPage` |
| **Staff Scanner** | `STAFF` | **PASS** | Manual QR check-in (`HỢP LỆ`), duplicate scan (`409` -> `TỪ CHỐI`), 1.5s debounce (`busyRef`), camera cleanup on unmount |
| **Admin Console** | `ADMIN` | **PASS** | All 5 tabs rendered; `Promise.allSettled` partial-failure resilience verified via `route.abort()` on `/api/notifications/logs` |

- **Console & Page Errors:** `0` uncaught JS exceptions (`PAGE_ERRORS: 0`); 4 console entries corresponded exclusively to intentional negative tests (`401`, `409`, and 2x `route.abort()`).
- **Physical Camera:** Not tested in headless CI (verified camera-unavailable fallback message in `StaffScannerPage`).
