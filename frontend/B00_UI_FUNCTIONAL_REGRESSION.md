# B00-UI Functional Regression Report

## Test Environment
- **Target Stack**: Isolated `pkb-test` (`docker-compose.test.yml` on `http://localhost:18080`) with newly built `pkb-test-web-frontend` image.
- **Runner**: Playwright (`playwright-core` + Chrome headless, isolated browser profile) via `verify_b00_ui.mjs`.
- **Backend / DB**: Unmodified Version B (`upgrade/soa-complete` @ `3f155efe1b8c48d751a24b9e6776932866e4e1b8`).

## Executed Functional Cases
| Area | Case | Result | Notes / Evidence |
| :--- | :--- | :--- | :--- |
| Customer | Landing booking CTA -> `/book` | PASS | Direct navigation from `Đặt sân ngay` CTA |
| Customer | 7-day date strip + slot selection (2 contiguous hours) | PASS | `08-booking-selected-summary.png` |
| Customer | Booking creation -> Checkout pending payment + VietQR | PASS | `09-checkout-pending.png` |
| Customer | Booking lookup (`/lookup`) & History (`/my-bookings`) | PASS | `14-lookup.png`, `15-history.png` |
| Auth | Registration (`/register`) | PASS | Created new member & redirected to `/` |
| Auth | Invalid credentials rejection (`401`) | PASS | Rendered error `AlertBanner` |
| Auth | Demo autofill separation (collapsed by default) | PASS | Verified hidden until toggle clicked |
| Auth | Logout & role-based navigation (Customer/Staff/Admin) | PASS | Verified redirects to `/`, `/staff/scanner`, `/admin` |
| Checkout (SOA) | Simulated payment -> `Payment received, booking pending` | PASS | Authentic state via stopped `rabbitmq-test` (`10-payment-received-booking-pending.png`) |
| Checkout (SOA) | `Booking confirmed, ticket pending` | PASS | Authentic state via stopped `checkin-qr-service` (`11-booking-confirmed-ticket-pending.png`) |
| Checkout (SOA) | Authentic QR Ticket Pass rendering | PASS | `12-qr-ticket.png` |
| Checkout (SOA) | Cancellation + signed webhook -> `COMPENSATION_REQUIRED` | PASS | `13-compensation-required.png` |
| Staff | Valid manual QR check-in (`bypass_time_check`) | PASS | `17-staff-checkin-success.png` (`HỢP LỆ — MỜI KHÁCH VÀO SÂN`) |
| Staff | Duplicate check-in rejection (`409`) | PASS | `TỪ CHỐI CHECK-IN` after 1.5s debounce |
| Staff | Physical camera scan | NOT RUN | Headless environment without physical webcam hardware |
| Admin | Overview, Branch/Location/Court, Pricing, Bookings, Accounts | PASS | `18-admin-overview.png` .. `22-admin-accounts.png` |
| Performance | Route code splitting (`html5-qrcode` excluded from initial HTML/chunk) | PASS | `index` chunk `253.56 kB` (`gzip 74.06 kB`), `StaffScannerPage` `345.13 kB` |
