# B02 Database Schema & Additive Migration

## 1. Additive Changes on `payment_db`

### Existing Table: `payment_transactions`
Idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` executed on `payment-service` startup (`services/payment-service/app/main.py`):
- `expected_amount INTEGER NOT NULL DEFAULT 0`
- `received_amount INTEGER NOT NULL DEFAULT 0`
- `refunded_amount INTEGER NOT NULL DEFAULT 0`
- `currency VARCHAR(10) NOT NULL DEFAULT 'VND'`
- `payment_mode VARCHAR(20) NOT NULL DEFAULT 'MOCK_DEMO'`
- `simulation_notice TEXT NOT NULL DEFAULT 'THANH TOAN GIA LAP'`
- `attempt_count INTEGER NOT NULL DEFAULT 0`
- `failure_reason TEXT`
- `last_attempt_at TIMESTAMPTZ`

Backfill statements for existing B01 rows:
- `UPDATE payment_transactions SET expected_amount = CAST(ROUND(amount) AS INTEGER) WHERE expected_amount = 0`
- `UPDATE payment_transactions SET received_amount = expected_amount WHERE status = 'SUCCEEDED' AND received_amount = 0`

### New Tables Created via `Base.metadata.create_all`
1. `payment_attempts`
2. `reconciliation_cases`
3. `refund_transactions`
4. `financial_audit_logs`

No destructive `DROP`, `TRUNCATE`, or column type changes are performed.
