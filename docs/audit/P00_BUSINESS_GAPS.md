# P00 — Real-World Business Gap Analysis

## 1. Business Capability Matrix

| Capability | Status | Code Evidence | Related Services |
| :--- | :---: | :--- | :--- |
| **Guest bookings** | **IMPLEMENTED** | `POST /api/bookings` uses `get_optional_claims` (`bookings.py:30-38`) | `court-booking-service`, `payment-service`, `checkin-qr-service` |
| **Registered customer bookings** | **IMPLEMENTED** | `user_id` linked when JWT present; `GET /api/bookings/my` (`bookings.py:41-53`) | `auth-service`, `court-booking-service` |
| **Walk-in bookings created by staff** | **MISSING** | No staff walk-in endpoint or UI; staff must use public booking form | `court-booking-service`, `frontend` |
| **Cash payments at the venue** | **MISSING** | Only VietQR bank transfer / demo webhook exists (`payment_service.py`) | `payment-service`, `court-booking-service` |
| **Online bank payments (real)** | **PARTIALLY IMPLEMENTED** | Static `img.vietqr.io` URL + HMAC webhook exist (`payment_service.py:26-42`), but no real bank/gateway integration (payOS/SePay); relies on `simulate-webhook` | `payment-service` |
| **Cancellation of unpaid bookings** | **IMPLEMENTED** (insecure) | `POST /api/bookings/{code}/cancel` cancels `PENDING_PAYMENT` (`bookings.py:126-146`) — lacks ownership check | `court-booking-service`, `payment-service` |
| **Cancellation of paid bookings** | **PARTIALLY IMPLEMENTED** | `POST /api/bookings/admin/{code}/cancel` cancels `PAID` bookings & revokes QR ticket (`bookings.py:78-95`), **but triggers no refund** | `court-booking-service`, `checkin-qr-service` |
| **Full and partial refunds** | **MISSING** | No refund model, status, API, or provider payout integration | `payment-service`, `court-booking-service` |
| **Rescheduling** | **MISSING** | No reschedule endpoint or slot-swap transaction | `court-booking-service` |
| **Court maintenance** | **PARTIALLY IMPLEMENTED** | `Court.status = 'MAINTENANCE'` blocks new bookings (`booking_service.py:310-311`), but does not handle existing paid bookings on that court | `court-booking-service` |
| **Unexpected court unavailability** | **MISSING** | No bulk cancel/reallocate/notify workflow when a court goes down | `court-booking-service`, `notification-service` |
| **Outdoor court weather disruptions** | **MISSING** | `Court.court_type` supports `OUTDOOR`, but no weather API, alerts, or rain-out policy | `court-booking-service`, `notification-service` |
| **No-show handling** | **MISSING** | No `NO_SHOW` status or post-slot sweep | `court-booking-service`, `checkin-qr-service` |
| **Booking completion** | **MISSING** | Paid bookings stay `PAID` forever; no `COMPLETED` transition | `court-booking-service` |
| **Payment reconciliation** | **MISSING** | No `provider_tx_id` uniqueness, no overpayment/underpayment ledger, no reconciliation report | `payment-service` |
| **Operational reporting** | **PARTIALLY IMPLEMENTED** | Basic `GET /api/bookings/admin/stats` (`bookings.py:70-75`), no date-range/branch/utilization/export reports | `court-booking-service` |
| **Customer notifications** | **PARTIALLY IMPLEMENTED** | Sends QR ticket email on `ticket.issued` (`email_service.py`), **no emails** for booking expiry, cancellation, refund, or weather alerts | `notification-service` |
| **Administrative audit history** | **MISSING** | No audit log table for admin/staff actions (cancellations, price changes, court edits, time-bypass check-ins) | All services |

---

## 2. Critical Business Logic Findings (CONFIRMED)

### BIZ-01 (P0): Ticket Issued on `payment.succeeded` Before Booking Confirmation
- **Service:** `checkin-qr-service` (`app/services/checkin_service.py:128-129`)
- **Current Behavior:** `checkin-qr-service` listens to `payment.succeeded` and immediately issues a `VALID` QR ticket. It does not wait for `court-booking-service` to confirm the booking (`booking.confirmed`).
- **Real-World Failure:** If a late payment succeeds after the booking expired and another customer already booked the slot, `checkin-qr-service` still emails a `VALID` QR ticket for a slot the customer does not own.
- **Recommended Minimal Fix:** Have `court-booking-service` validate `status == "PENDING_PAYMENT"` and publish `booking.confirmed` (or `booking.confirmation_failed` for refund) upon consuming `payment.succeeded`; have `checkin-qr-service` issue tickets on `booking.confirmed`.
- **Suggested Phase:** P01

### BIZ-02 (P1): Hardcoded Fallback Pricing & No Maintenance Rebooking Guard
- **Service:** `court-booking-service` (`app/services/booking_service.py:224-229`)
- **Current Behavior:** `_find_slot_price` falls back to `200000` / `120000` VND if no `PricingRule` matches.
- **Recommended Minimal Fix:** Raise explicit `500`/`400` configuration error if pricing rule is missing rather than silently charging a hardcoded price.
- **Suggested Phase:** P02
