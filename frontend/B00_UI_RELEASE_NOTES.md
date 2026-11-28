# Version B Release Notes — Premium UI 2.0 Development Preview

**Branch**: `upgrade/soa-complete`  
**Status**: Enhanced Development Preview (Not Production-Ready)

## 1. What Is Included in Version B
Version B (`upgrade/soa-complete`) combines the **B00/P01 distributed transaction reliability baseline** (transactional outbox/inbox, idempotent webhook processing, compensation-required tracking, out-of-order cancellation guard, and isolated test harness) with **Premium UI 2.0**:
- **Original Brand Identity**: Custom SVG `BrandMark` & `BrandLockup`, matching `favicon.svg`, local SIL OFL fonts (`Bricolage Grotesque Variable`, `Be Vietnam Pro`, `JetBrains Mono`), and Contemporary Athletic Club color tokens.
- **Public Landing & Split-Screen Auth**: Dedicated editorial landing page (`/`) with Pickleball photography (`Hình ảnh minh họa`) and real branch/court counts; split-screen `/login` and `/register` with collapsed-by-default presentation demo controls.
- **Booking & Asynchronous Checkout**: 7-day local-calendar date strip, branch/location/court-type filters, structured court cards, transaction-style summary, 4-step SOA checkout progress strip, and `COMPENSATION_REQUIRED` reconciliation warning.
- **Digital Venue Pass & Operations**: Branded QR ticket pass (`QrTicketCard`), touch-friendly Staff QR Scanner (`/staff/scanner`), and responsive Admin sidebar console (`/admin`).

## 2. Verified Regression Summary
- **B00-UI & B00-UI-V Playwright Suites (Isolated `pkb-test`)**: Verified customer landing/booking/checkout/lookup/history, asynchronous SOA states (payment received pending booking, confirmed pending ticket, QR ticket, compensation-required), staff manual QR check-in & duplicate rejection, admin pricing update & account creation, and `0` horizontal overflow across `375×812`, `390×844`, `768×1024`, `1280×800`, `1440×900`, and `1920×1080`.
- **Production Build**: `tsc && vite build` and `docker build ./frontend` succeeded with `html5-qrcode` isolated in the lazy-loaded `StaffScannerPage` chunk.

## 3. Explicit Disclosures & Known Limitations
- **Not Production-Ready**: Version B is an enhanced development preview; further backend enhancements (`B01`+) will follow.
- **Payment Integration Pending**: Real payment provider integration remains pending; the checkout webhook simulator is strictly a development/demo mechanism.
- **Security Hardening Pending**: Full production security hardening remains pending.
- **Physical Camera Scan**: Not executed in headless CI/verification environments lacking webcam hardware.

## 4. Environment & Safe Startup
- Copy `.env.example` to `.env` only if `.env` does not already exist.
- Start with `docker compose up -d --build`.
- **Version A vs. Version B Isolation**: `main` (Version A) and `upgrade/soa-complete` (Version B) differ in additive database schemas (`outbox_events`, `inbox_events`, `booking_compensations`, `cancelled_bookings`, `reconciliation_status`) and RabbitMQ `.v2` queues. Use a separate checkout and isolated Docker Compose project/volumes when comparing both versions; never delete existing volumes.
