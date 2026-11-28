# UI02 — Visual & Responsive QA Report

**Browser:** Headless Google Chrome `158.0.8127.38` via isolated Playwright (`%TEMP%\pw_ui02`)  
**Test Environment:** Isolated `pkb-ui02-test` (`http://localhost:18080`) using `main` backend + UI01/UI02 frontend.

## 1. Visual Findings & Polish Applied

1. **Mobile Filter `<select>` Horizontal Overflow (FIXED):**
   - *Observed:* On `375x812` and `390x844` viewports, `BookingPage` had `scrollWidth=473 > innerWidth` because long branch/location `<option>` labels stretched `#filter-location` beyond the card width.
   - *Fix (`frontend/src/pages/BookingPage.tsx`):* Changed filter container to `flex-col sm:flex-row` and `<select>` controls to `w-full sm:w-auto max-w-full min-w-0`.
   - *Re-verification:* `0` overflows across all 6 viewports × 5 routes (`overflows=[]`).
2. **Admin Initial Loading State (FIXED):**
   - *Observed:* `AdminDashboardPage` rendered `LoadingSkeleton` above an empty `Bước 1` section during initial load.
   - *Fix (`frontend/src/pages/AdminDashboardPage.tsx`):* Wrapped tab body in `loading && branches.length === 0 ? <LoadingSkeleton rows={4} /> : (...)`.
3. **Route-Level Code Splitting (FIXED):**
   - *Observed:* Single JS bundle was `618.82 kB` (`gzip: 180.91 kB`).
   - *Fix (`frontend/src/App.tsx`):* Lazy-loaded `CheckoutPage`, `StaffScannerPage`, and `AdminDashboardPage` via `React.lazy` + `Suspense`.
   - *Result:* Main customer bundle dropped to `224.49 kB` (`gzip: 67.96 kB`), with zero Vite chunk warnings.

## 2. Responsive Matrix (6 Viewports × 5 Routes)

| Viewport | `/` | `/login` | `/checkout/:code` | `/staff/scanner` | `/admin` | Result |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `375 × 812` | PASS | PASS | PASS | PASS | PASS | `0` overflow |
| `390 × 844` | PASS | PASS | PASS | PASS | PASS | `0` overflow |
| `768 × 1024` | PASS | PASS | PASS | PASS | PASS | `0` overflow |
| `1280 × 800` | PASS | PASS | PASS | PASS | PASS | `0` overflow |
| `1440 × 900` | PASS | PASS | PASS | PASS | PASS | `0` overflow |
| `1920 × 1080` | PASS | PASS | PASS | PASS | PASS | `0` overflow |

## 3. Screenshots Captured (`c:\Users\Dell\SOA_Final\finalProjectSOA_ui02_screenshots\`)
- `01_booking_desktop.png`, `01b_booking_mobile_390.png`, `02_login.png`, `03_register.png`, `04_checkout_pending.png`, `05_qr_ticket.png`, `06_lookup.png`, `07_my_bookings.png`, `08_staff_scanner.png`, `09_admin_courts.png`, `10_admin_pricing.png`, `11_admin_bookings.png`, `12_admin_emails.png`, `13_admin_accounts.png`.
