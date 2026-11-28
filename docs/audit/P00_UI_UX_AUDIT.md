# P00 — Frontend UI/UX Audit

> [!NOTE]
> **Visual Inspection Status:** Live browser inspection at `http://localhost:8080` was **BLOCKED** (`DevToolsActivePort` not found at `C:\Users\Dell\AppData\Local\Google\Chrome\User Data\DevToolsActivePort`). All findings below are derived from **static code inspection** of `frontend/` (`index.html`, `package.json`, `tailwind.config.js`, and all 14 files in `frontend/src/`). No screenshots were captured.

---

## 1. Inspected Frontend Pages & Components

| File | Role | Lines |
| :--- | :--- | :---: |
| `frontend/src/App.tsx` | Router (`/`, `/login`, `/register`, `/checkout/:bookingCode`, `/lookup`, `/my-bookings`, `/staff/scanner`, `/admin`) | 40 |
| `frontend/src/api/client.ts` | Fetch wrapper, JWT `localStorage` helpers, `formatVND`, `todayVN` | 52 |
| `frontend/src/context/AuthContext.tsx` | Auth state & `/api/auth/me` hydration | 77 |
| `frontend/src/components/Navbar.tsx` | Top navigation bar with role-based links | 91 |
| `frontend/src/pages/BookingPage.tsx` | Court availability calendar, contiguous slot picker, guest/user booking form | 452 |
| `frontend/src/pages/CheckoutPage.tsx` | 15-min countdown, VietQR display, 2.5s polling, Demo Webhook, QR ticket view | 360 |
| `frontend/src/pages/LoginPage.tsx` | Login form + 1-click demo credential buttons | 122 |
| `frontend/src/pages/RegisterPage.tsx` | Customer registration form | 108 |
| `frontend/src/pages/LookupAndHistoryPage.tsx` | Public booking lookup (`/lookup`) & customer history (`/my-bookings`) | 177 |
| `frontend/src/pages/StaffScannerPage.tsx` | `html5-qrcode` camera scanner, manual entry, bypass-time toggle, recent logs | 270 |
| `frontend/src/pages/AdminDashboardPage.tsx` | KPI cards + 4 tabs (Branches/Locations/Courts, Pricing, Bookings, Notification Logs) | 965 |

---

## 2. UI/UX & Contract Findings

| ID | Sev | Area | Location | Finding & Minimal Fix |
| :--- | :---: | :--- | :--- | :--- |
| **UI-01** | **P1** | Error Handling | `frontend/src/api/client.ts:38-39` | FastAPI 422 returns `detail` as an array of objects, causing `new Error(errObj?.detail)` to render `[object Object]` in UI banners. Fix: parse `Array.isArray(errObj.detail)` and join `.msg`. |
| **UI-02** | **P1** | Checkout Polling | `frontend/src/pages/CheckoutPage.tsx:23-28,53-62` | 2.5s polling interval calls `POST /api/payments/create` repeatedly while `PENDING_PAYMENT`. Fix: call `POST /api/payments/create` once, then poll `GET /api/payments/booking/{bookingCode}` or `GET /api/bookings/lookup/{bookingCode}`. |
| **UI-03** | **P2** | Silent Error State | `frontend/src/pages/LookupAndHistoryPage.tsx:103-105` | `MyBookingsPage` has no `.catch()` on `GET /api/bookings/my`; API/auth errors silently render empty state `"Bạn chưa có đơn đặt sân nào."`. Fix: add error banner + retry button. |
| **UI-04** | **P2** | Demo UI Exposure | `frontend/src/pages/CheckoutPage.tsx:337-345`, `LoginPage.tsx:90-111`, `StaffScannerPage.tsx` | Demo webhook button, demo login autofill buttons, and `bypass_time_check` checkbox are unconditionally rendered. Fix: gate behind build/runtime config flag (`VITE_ENABLE_DEMO_CONTROLS` or backend `/config`). |
| **UI-05** | **P2** | Missing 404 & Admin Users UI | `frontend/src/App.tsx`, `AdminDashboardPage.tsx` | No `*` catch-all 404 route; `auth-service` `GET/POST /api/auth/users` is not wired into `AdminDashboardPage`. |
| **UI-06** | **P2** | Accessibility (a11y) | `AdminDashboardPage.tsx:441,536`, forms across pages | Clickable `<div>` cards lack `role="button"`, `tabIndex`, and keyboard handlers; most `<label>` elements lack `htmlFor`/`id` bindings. |
| **UI-07** | **P3** | Client Validation & Loading | `RegisterPage.tsx`, `BookingPage.tsx`, `AdminDashboardPage.tsx` | Client forms omit `minLength={2}` (name) and `minLength={8}` (phone) required by backend; `AdminDashboardPage` lacks initial loading state. |

---

## 3. Recommended Sports-Club Design Direction (For Future Phases)

Keep the current Vietnamese language and core emerald/slate palette, while elevating from generic Tailwind utility cards to a cohesive **Pickleball Club & Court Operations** identity:
- **Typography:** Pair a crisp geometric display font (e.g., `Plus Jakarta Sans` or `Be Vietnam Pro` with full Vietnamese diacritics) with `JetBrains Mono` for booking codes, countdowns, and pricing.
- **Court Timeline:** Visual court-row × hour-column availability matrix on desktop (and compact court-card pill selector on mobile) with clear peak-hour badges, maintenance hatches, and 15-min hold indicators.
- **Role-Focused Workspaces:** Keep customer booking/checkout clean and distraction-free; give Staff Scanner a high-contrast, thumb-friendly mobile layout with instant audio/visual feedback; give Admin a structured operations console.
