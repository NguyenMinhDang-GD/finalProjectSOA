# Version A Release Notes — Premium UI 2.0 on Original Backend

**Branch**: `main`  
**Backend Baseline**: Original five-microservice backend (`bfa1535f1e754bd654b174a23ceb08d4f1b1c8cc` backend)  
**Frontend**: Premium UI 2.0 (adapted to original `main` API contracts)

## 1. Visual & UX Scope on `main`
Version A (`main`) delivers the full **Premium UI 2.0** experience on top of the original backend:
- **Brand Identity**: Custom SVG `BrandMark` & `BrandLockup`, matching `favicon.svg`, locally bundled SIL OFL fonts (`Bricolage Grotesque Variable`, `Be Vietnam Pro`, `JetBrains Mono`), and Contemporary Athletic Club tokens.
- **Customer Experience**: Asymmetric editorial landing page (`/`), split-screen `/login` & `/register` with collapsed presentation demo controls, 7-day booking date strip & redesigned court cards (`/book`), 4-step checkout & branded QR pass (`/checkout/:code`), lookup (`/lookup`), and member history (`/my-bookings`).
- **Operational Workspaces**: Touch-friendly Staff QR Scanner (`/staff/scanner`) and responsive Admin sidebar console (`/admin`), with single-line `1280px` navbar alignment.

## 2. Original Backend Limitations (vs. Version B `upgrade/soa-complete`)
Because `main` preserves the original backend without B00/P01 reliability enhancements:
- **No `COMPENSATION_REQUIRED` Reconciliation**: `PaymentTransaction` on `main` does not include `reconciliation_status` or `reconciliation_note`, so cancelled/expired bookings do not render compensation reconciliation banners.
- **No Transactional Outbox/Inbox or Out-of-Order Cancellation Guard**: Event delivery and idempotency rely on the original RabbitMQ handlers rather than Version B's `outbox_events` / `inbox_events` / `cancelled_bookings` tables.
- **Demo Payment & Security**: Simulated VietQR webhook is for demonstration only; real payment integration and full security hardening are not part of `main`.
