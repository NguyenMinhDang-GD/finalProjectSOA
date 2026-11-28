# P01 / Version B — Safe Rollback Instructions (R07 Updated)

> [!IMPORTANT]
> Switching Git branches (`git checkout main`) rolls back **source code only**. It does **not** reverse PostgreSQL schema additions or RabbitMQ `.v2` queue/DLQ declarations.

## 1. Source-Code & Container Rollback (Non-Destructive)

```powershell
git checkout main
docker compose up -d --build
```

## 2. Database Schema Compatibility
- All P01 tables (`outbox_events`, `inbox_events`, `booking_compensations`, `payment_compensations`) and columns (`reconciliation_status`, `reconciliation_note`) are **strictly additive**.
- Existing `main` services ignore these additive tables/columns while preserving 100% of existing bookings, payments, tickets, and users.
- **Precaution:** Do not drop `outbox_events` or compensation tables during an emergency rollback, as they may hold audit/reconciliation evidence.

## 3. RabbitMQ Topology Compatibility
- P01 declares `.v2` consumer queues (`booking.payment_events.v2`, `payment.booking_events.v2`, `checkin.events.v2`) and `pickleball.dlx` / `pickleball.dlq`.
- **Precaution:** Before rolling back to `main`, drain or inspect any unconsumed messages in `.v2` queues and `pickleball.dlq` so in-flight events are not stranded when `main` resumes consuming the original queue names.
