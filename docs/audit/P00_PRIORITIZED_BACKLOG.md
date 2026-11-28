# P00 — Prioritized Implementation Backlog

> Prioritized for academic defense and production-like reliability: **Financial Correctness → Reservation Integrity → Distributed Transaction Recovery → Security → Real-World Operations → UI/UX Polish**.

---

## 1. Deadline-Critical Phases (Must-Have for Defense & Reliable Demo)

| Phase | ID | Priority | Item | Services |
| :--- | :---: | :---: | :--- | :--- |
| **P01** | **ARCH-01** | **P0** | Implement **Transactional Outbox** (or atomic outbox table + relay) in `court-booking-service`, `payment-service`, `checkin-qr-service` + fail loudly when RMQ `exchange` is `None`. | `booking`, `payment`, `checkin` |
| **P01** | **ARCH-02** | **P0** | Configure `pickleball.dlx` / `pickleball.dlq` and bounded retry on `booking.payment_events`, `payment.booking_events`, `checkin.events`. | `booking`, `payment`, `checkin` |
| **P01** | **ARCH-03 / BIZ-01** | **P0** | Fix **expiration vs late-payment race**: reject expired payments in `payment-service`; emit `booking.confirmed` / `booking.confirmation_failed` from `court-booking-service`; issue QR tickets in `checkin-qr-service` **only on `booking.confirmed`**. | `payment`, `booking`, `checkin` |
| **P01** | **ARCH-04 / ARCH-05** | **P1** | Use Lua ownership-checked Redis lock release (`GET == token -> DEL`) and `FOR UPDATE SKIP LOCKED` in `run_expiration_worker`. | `court-booking-service` |
| **P01** | **TEST-01** | **P1** | Create isolated `docker-compose.test.yml` + automated `pytest` concurrency & saga tests (double-booking, expiration vs webhook, idempotency). | `tests/` |
| **P02** | **SEC-01 / SEC-02 / SEC-03** | **P0** | Fix **IDOR & enumeration**: increase `booking_code` entropy (`>= 8` chars), require JWT owner or signed guest access token for `lookup`, `cancel`, `payments`, and `ticket` endpoints. | `booking`, `payment`, `checkin`, `frontend` |
| **P02** | **SEC-04 / SEC-11** | **P0** | Gate `simulate-webhook` (`ENABLE_DEMO_WEBHOOK=false` by default in prod or `ADMIN`-only) and `ALLOW_DEMO_BYPASS_TIME`. | `payment`, `checkin`, `frontend` |
| **P02** | **SEC-06..SEC-10** | **P1** | Lock down CORS (`FRONTEND_ORIGIN`), add Nginx `limit_req` rate limiting, bind internal DB/Redis/RMQ ports to `127.0.0.1` or internal network, HTML-escape email templates, constant-time `X-Internal-Key`. | All services, `infra/` |
| **P03** | **EXT-01** | **P1** | Integrate **payOS** (or **SePay**) real VietQR + signed webhook behind a clean `PaymentProvider` interface, keeping demo mode strictly opt-in for offline defense. | `payment-service` |
| **P03** | **EXT-02** | **P1** | Configure **Brevo SMTP** (or Gmail App Password) behind email provider config + fix `NotificationLog` duplicate-send race with DB unique constraint. | `notification-service` |
| **P03** | **BIZ-CASH / WALKIN** | **P1** | Add **Staff Walk-in Booking** & **Cash Payment at Venue** (`STAFF`/`ADMIN` only) + **Booking Completion / No-Show** transitions. | `booking`, `payment`, `frontend` |

---

## 2. High-Value Operational & UX Enhancements (Post-Core)

| Phase | ID | Priority | Item | Services |
| :--- | :---: | :---: | :--- | :--- |
| **P04** | **UI-01..UI-07** | **P2** | Fix 422 `[object Object]` error parsing, stop `POST /api/payments/create` polling loop, add `MyBookingsPage` error handling, add 404 route, wire `AdminDashboardPage` user management (`GET/POST /api/auth/users`), fix a11y labels/buttons. | `frontend` |
| **P04** | **BIZ-REP** | **P2** | Add **Cancel Paid Booking + Refund/Credit record** + **Payment Reconciliation** (`provider_tx_id` unique index) + **Admin Audit Log**. | `payment`, `booking`, `frontend` |
| **P05** | **EXT-03** | **P3** | Integrate **Open-Meteo** weather forecast alerts for `OUTDOOR` courts (with CC BY 4.0 attribution). | `booking`, `notification`, `frontend` |
| **P05** | **OPT-PUSH** | **P3** | Optional Web Push notifications (VAPID) for booking confirmation/reminders. | `notification`, `frontend` |
