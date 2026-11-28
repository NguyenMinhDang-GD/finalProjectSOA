# B03 — Migration & Rollback Verification

## 1. Upgrade Path Tested (`soa-b02-checkpoint` → B03)
Verified via isolated script `run_b03_migration.py` (`pkb-b03-mig` project, temporary detached worktree at `219531abeff4bd78adee175861c67859804b6c08`):

1. Booted `soa-b02-checkpoint` stack and seeded representative B02 records (`PKB-B02-MIG-001` in `booking_orders`, `booking_slots`, `payment_transactions`).
2. Upgraded services in-place to B03 (`court-booking-service`, `payment-service`, `checkin-qr-service`, `notification-service`, `web-frontend`, `api-gateway`).
3. Verified existing row counts remained 100% intact (`bookings`, `payments`) and new columns defaulted cleanly (`booking_source:booking_revision = ONLINE:1`, `payment_method:booking_revision = SIMULATED_ONLINE:1`).
4. Verified all 3 new B03 tables created (`booking_reschedule_history`, `maintenance_blocks`, `operational_audit_logs`) and `uq_notification_sent_booking` dropped cleanly in `notification_db`.
5. Restarted `court-booking-service`, `payment-service`, `checkin-qr-service` and confirmed all services returned healthy (`B03_MIGRATION_AND_RESTART_OK`, exit 0).

## 2. Rollback Strategy
- All B03 schema additions are additive (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`).
- Rolling back application containers to `soa-b02-checkpoint` (`219531abeff4bd78adee175861c67859804b6c08`) leaves existing B02 rows readable and functional, **with the caveat** that B03-specific booking states (`NO_SHOW`, `COMPLETED`) and B03-only events (`booking.rescheduled`, `booking.no_show`, `booking.completed`) cannot be processed by older B02 containers and must be drained or handled before downgrading.
