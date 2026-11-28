# P00 — Security, Mock & External API Audit

## 1. Security Findings (Classified P0–P3)

| ID | Sev | Category | Service & Location | Finding & Minimal Fix | Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **SEC-01** | **P0** | IDOR / Unauth Cancel | `court-booking-service` `routers/bookings.py:126-146` | `POST /api/bookings/{booking_code}/cancel` has **no auth or ownership check**. Anyone can cancel any unpaid booking. Fix: require JWT owner (`user_id == sub`) or signed guest-access token. | CONFIRMED |
| **SEC-02** | **P0** | IDOR / PII Leak | `court-booking-service` `routers/bookings.py:98-107`, `checkin-qr-service` `routers/checkin.py:14-21` | `GET /api/bookings/lookup/{code}` and `GET /api/checkin/ticket/{code}` are **unauthenticated** and return full customer PII (`name`, `email`, `phone`) + signed QR payload/image. Fix: require JWT owner or short-lived lookup token (e.g., email/phone verification or HMAC token in checkout URL). | CONFIRMED |
| **SEC-03** | **P0** | Low-Entropy Enumeration | `court-booking-service` `services/booking_service.py:112-114` | `_generate_booking_code` uses `secrets.token_hex(2)` (only 65,536 codes/day), enabling trivial brute-force enumeration of `lookup`, `cancel`, `payments`, and `ticket` endpoints. Fix: increase to >= 8–10 random bytes/alphanumeric chars + add Nginx rate limiting. | CONFIRMED |
| **SEC-04** | **P0** | Unauth Demo Payment | `payment-service` `config.py:14`, `routers/payments.py:53-63` | `ENABLE_DEMO_WEBHOOK=true` by default exposes unauthenticated `POST /api/payments/simulate-webhook/{code}`, allowing anyone to mark any booking `PAID` for free. Fix: default `false` in non-dev, require `ADMIN` role or disable in production. | CONFIRMED |
| **SEC-05** | **P1** | Unauth Payment Create/Read | `payment-service` `routers/payments.py:19-31` | `POST /api/payments/create` and `GET /api/payments/booking/{code}` have no auth/ownership check. | CONFIRMED |
| **SEC-06** | **P1** | Hardcoded Default Secrets | All 5 `app/config.py` + `.env.example` | Default fallback secrets (`jwt_secret`, `qr_hmac_secret`, `webhook_secret`, `internal_api_key`, DB/RMQ creds) are hardcoded in Python `Settings` classes. Fix: fail fast in production if secrets are missing/default. | CONFIRMED |
| **SEC-07** | **P1** | Permissive CORS | All 5 `app/main.py` | `allow_origins=["*"]` with `allow_credentials=True`. Fix: restrict to configured `FRONTEND_ORIGIN`. | CONFIRMED |
| **SEC-08** | **P1** | Direct Port & Infra Exposure | `docker-compose.yml` | Ports `5432`, `6379`, `5672`, `15672`, `8001–8005` are bound to `0.0.0.0` on host; Redis has no password; RabbitMQ uses `guest:guest`. Fix: bind internal ports to `127.0.0.1` or keep on `pkb-net` only; set Redis/RMQ passwords. | CONFIRMED |
| **SEC-09** | **P1** | No Nginx Rate Limiting | `infra/gateway/nginx.conf` | No `limit_req_zone` on `/api/auth/login`, `/api/bookings/lookup`, `/api/payments/webhook`. | CONFIRMED |
| **SEC-10** | **P1** | HTML Injection in Email | `notification-service` `services/email_service.py:75-108` | Customer/court fields interpolated raw into HTML email f-string without `html.escape()`. | CONFIRMED |
| **SEC-11** | **P2** | Demo Time Bypass Default | `checkin-qr-service` `config.py:11` | `ALLOW_DEMO_BYPASS_TIME=true` by default lets staff bypass check-in time windows. | CONFIRMED |
| **SEC-12** | **P2** | Non-constant-time Key & `is_active` Gap | `court-booking-service/app/security.py:44-46`, `auth-service/app/routers/auth.py:30-35` | `!=` used for `X-Internal-Key` instead of `hmac.compare_digest`; `/me` and JWT checks do not verify `user.is_active`. | CONFIRMED |
| **SEC-13** | **P2** | PII in Logs | `notification-service` `email_service.py:161` | Plaintext `recipient_email` logged at INFO level. | CONFIRMED |
| **SEC-14** | **P3** | Ngrok Free-Tier Exposure | `docker-compose.yml:270-282` | Exposes entire gateway (including demo endpoints if enabled) publicly over HTTPS when `tunnel` profile is active. | CONFIRMED |

---

## 2. Mock, Demo & Hardcode Inventory

| Type | Location | Details | Classification |
| :--- | :--- | :--- | :--- |
| **Demo Webhook** | `payment-service/app/routers/payments.py:53-63` | `simulate-webhook/{booking_code}` fakes bank confirmation | **Incomplete Production Feature** (replace with real gateway) |
| **Static VietQR URL** | `payment-service/app/services/payment_service.py:26-30` | Constructs `img.vietqr.io` URL; no bank API or transaction verification | **Mock / Template** |
| **Check-in Time Bypass** | `checkin-qr-service/app/config.py:11` | `allow_demo_bypass_time = True` | **Demo Helper** |
| **Mailpit SMTP** | `docker-compose.yml:51-59`, `.env.example:22-27` | Local catch-all SMTP server (`mailpit:1025`) | **Dev/Demo Fixture** |
| **Seeded Accounts** | `auth-service/app/services/auth_service.py:16-34`, `LoginPage.tsx:90-111` | `admin@pickleball.vn`, `staff@pickleball.vn`, `khachhang@pickleball.vn` | **Demo Seed Data** |
| **Hardcoded Fallback Bank/Branch** | `CheckoutPage.tsx:307-326`, `email_service.py:35-36` | Fallback strings `'SAN PICKLEBALL SOA'`, `'0123456789'`, `'Chi nhánh 1'` | **Hardcoded Fallback** |
| **Hardcoded Fallback Price** | `booking_service.py:224-229` | `200000` / `120000` if no `PricingRule` found | **Hardcoded Fallback** |
| **TODO / FIXME** | Entire inspected codebase | None found | - |

---

## 3. External API Replacement Evaluation (Verified Against Official Docs)

| Capability | Candidate | Verified Capabilities & Limits | Prerequisites & Constraints |
| :--- | :--- | :--- | :--- |
| **Real Bank Payment** | **payOS** (`payos.vn/docs`) | Real-time VietQR A2A webhook with `signature` verification; **Payout API** supports automated refunds/disbursements; free/sponsored tiers (e.g., `Free-100`, `Pioneer-500`, partner bank promos). | Merchant account at `my.payos.vn`, linked VN bank account, `Client ID` / `API Key` / `Checksum Key`, public **HTTPS** webhook URL. |
| **Real Bank Payment** | **SePay** (`developer.sepay.vn`) | Real-time `Money in` webhook (HMAC-SHA256 / API Key / OAuth2) with 7x Fibonacci retry; 0% transaction fee, subscription plans (~50k–99k VND/mo). **Refunds:** *Unverified / not native gateway refund* (A2A bank monitoring). | SePay account, linked bank account, API token/webhook secret, public **HTTPS** webhook URL. |
| **Real Email Delivery** | **Brevo** (`brevo.com`) | SMTP relay (TLS 587/465) & Transactional API (`/v3/smtp/email`); **Free tier: 300 emails/day** (shared pool, Brevo footer branding on free tier, 429 on limit). | Brevo account, verified sender domain/email, SMTP key or API key. |
| **Weather Forecasting** | **Open-Meteo** (`open-meteo.com`) | **Free non-commercial tier** (no API key, CC BY 4.0 attribution required, 600 calls/min, 5k/hr, 10k/day). Commercial use requires paid plan (`customer-api.open-meteo.com`). | Branch/location latitude & longitude; attribution link if using free non-commercial tier for academic demo. |
| **Web Push (Optional)** | Browser Push API + VAPID (`pywebpush`) | Standards-based, no paid SaaS required. | HTTPS origin (works on `localhost` or `ngrok`), Service Worker, VAPID keypair. |
