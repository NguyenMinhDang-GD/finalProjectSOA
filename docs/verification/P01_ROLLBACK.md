# P01 — Safe Rollback Instructions

## 1. Code Rollback (Non-Destructive)

To revert the P01 code changes without altering Git history or deleting databases/volumes:

```powershell
git checkout main
docker compose up -d --build
```

## 2. Database & Queue Compatibility

- **Databases:** All P01 tables (`outbox_events`, `inbox_events`, `booking_compensations`, `payment_compensations`) and columns (`reconciliation_status`, `reconciliation_note`) are additive. Rolling back to `main` ignores these tables/columns while preserving all existing bookings, payments, tickets, and users.
- **RabbitMQ:** P01 uses `.v2` consumer queues (`booking.payment_events.v2`, `payment.booking_events.v2`, `checkin.events.v2`). Legacy queues were not deleted. Rolling back to `main` resumes consuming on the original queues.
