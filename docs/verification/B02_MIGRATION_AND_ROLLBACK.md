# B02 Migration & Safe Rollback Limitations (V07 / V08)

## 1. Isolated Migration & Restart Verification (V07)

Executed on isolated `pkb-b02-mig` from `soa-b01-checkpoint` (`0da0f45bb9b10926df302009d6e050feca8f695a`) -> B02-V:
- Seeded B01 rows: `PKB-MIG-SUCC-001` (`SUCCEEDED`, `150000.00`), `PKB-MIG-PEND-002` (`PENDING`, `200000.00`), `PKB-MIG-EXP-003` (`EXPIRED`, `COMPENSATION_REQUIRED`), `payment_compensations`, `outbox_events`, and `inbox_events`.
- Pre-migration and post-migration counts matched identically (`users`, `courts`, `payment_transactions`, `payment_compensations`).
- Backfill verified: `PKB-MIG-SUCC-001` -> `expected_amount=150000`, `received_amount=150000`; `PKB-MIG-PEND-002` -> `expected_amount=200000`, `received_amount=0`.
- All 4 new tables created (`payment_attempts`, `reconciliation_cases`, `refund_transactions`, `financial_audit_logs`).
- Restart test: updated `PKB-MIG-SUCC-001` to `received_amount=220000`, `refunded_amount=50000`, inserted a `payment_attempts` row, restarted `payment-service`, `court-booking-service`, `checkin-qr-service`, and verified `150000:220000:50000` and `attempts=1` were preserved without re-backfill or duplication.

## 2. Rollback Compatibility & Limitations (V08)

Additive PostgreSQL schema changes (`ADD COLUMN IF NOT EXISTS` and new tables) allow **source-code rollback** to `soa-b01-checkpoint` without breaking B01 SQL queries, **HOWEVER**:

- **Business-State Compatibility**: B01 code has **no knowledge** of `refund_transactions`, `reconciliation_cases`, `payment_attempts`, `financial_audit_logs`, or `booking_orders.admission_status`. Rolling back to B01 while B02 financial state exists means pending or partially completed refunds, open reconciliation cases, and `admission_status` locks will **not** be processed or enforced by B01 services.
- **Event-Contract Compatibility**: B01 services do not emit or consume `refund.requested`, `refund.succeeded`, `refund.failed`, or `payment.reconciliation_required`, though existing `.v2` queues (`payment.booking_events.v2`, `checkin.events.v2`) remain compatible with B01 `booking.confirmed` / `booking.cancelled` / `booking.expired`.
- **Safe Operational Rollback Procedure**:
  1. Freeze new refunds/cancellations (`PAYMENT_MODE=DISABLED` or maintenance mode) before rolling back application containers.
  2. Never `DROP` or `DELETE` `refund_transactions`, `reconciliation_cases`, `payment_attempts`, or `financial_audit_logs` during rollback — preserve all financial evidence in `payment_db`.
  3. Reconcile any in-flight `REQUESTED`/`APPROVED`/`PROCESSING` refunds manually or re-deploy B02 before resuming financial operations.
