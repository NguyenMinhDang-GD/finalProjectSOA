# B03 — Booking Rescheduling Design

## 1. Policy Rules
- **Unpaid (`PENDING_PAYMENT`)**: May reschedule to any contiguous available slot on active courts if not within `reschedule_cutoff_hours` (2h) for non-staff actors. Price is recalculated and synced to `payment-service` (`/api/payments/internal/{code}/sync-revision`).
- **Paid (`PAID`)**: May reschedule only when `admission_status == "NONE"` and new slot total price matches `total_amount` (`same_price == True`). Different-price changes are rejected (`400`) with cancel-and-rebook guidance.
- **Terminal / Admitted States**: `CANCELLED`, `EXPIRED`, `NO_SHOW`, `COMPLETED`, or `admission_status == "ADMITTED"` are blocked from rescheduling (`409`).

## 2. Concurrency & Ticket Revision Flow

```mermaid
sequenceDiagram
    participant C as Customer/Staff
    participant CBS as court-booking-service
    participant PG as PostgreSQL (booking_db)
    participant RD as Redis Locks
    participant PAY as payment-service
    participant QR as checkin-qr-service

    C->>CBS: POST /api/bookings/{code}/reschedule
    CBS->>PG: SELECT BookingOrder FOR UPDATE + sorted Court FOR UPDATE
    CBS->>RD: Acquire new slot locks (with owner token)
    CBS->>PG: Check MaintenanceBlock & BookingSlot conflicts
    CBS->>PG: Update BookingOrder (rev+1), replace BookingSlot rows, insert BookingRescheduleHistory & Outbox (booking.rescheduled)
    CBS->>RD: Release old slot locks
    alt status == PENDING_PAYMENT
        CBS->>PAY: POST /internal/{code}/sync-revision
    end
    CBS-->>QR: Outbox -> RabbitMQ booking.rescheduled
    QR->>QR: Update ticket booking_revision & new QR (r{rev}), invalidate rev-1 QR
```
