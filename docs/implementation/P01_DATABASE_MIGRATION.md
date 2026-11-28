# P01 — Database Schema Evolution

All P01 schema changes are **additive** and applied automatically on service startup via SQLAlchemy `Base.metadata.create_all` plus idempotent `IF NOT EXISTS` DDL statements in `app/main.py`. No existing tables, columns, or records are dropped or modified destructively.

## 1. New Tables

| Database | Table | Purpose & Key Constraints |
| :--- | :--- | :--- |
| `booking_db`, `payment_db`, `checkin_db` | `outbox_events` | Durable event outbox; index `ix_*_outbox_pending (status, next_retry_at, created_at)` |
| `booking_db`, `payment_db`, `checkin_db`, `notification_db` | `inbox_events` | Durable consumer deduplication; `UNIQUE (consumer_name, event_id)` |
| `booking_db` | `booking_compensations` | Compensation-required ledger; `UNIQUE (booking_code, payment_id)` |
| `payment_db` | `payment_compensations` | Received-funds compensation evidence; `UNIQUE (booking_code, provider_tx_id)` |

## 2. Additive Column & Index Changes

- **`payment_db.payment_transactions`:**
  - `reconciliation_status VARCHAR(40) NOT NULL DEFAULT 'NONE'`
  - `reconciliation_note TEXT`
  - Partial unique index: `uq_payment_provider_tx_id ON payment_transactions (provider_tx_id) WHERE provider_tx_id IS NOT NULL`
- **`notification_db.notification_logs`:**
  - Partial unique index: `uq_notification_sent_booking ON notification_logs (booking_code) WHERE status = 'SENT'`

## 3. Compatibility & Rollback Notes

- Existing `payment_transactions` rows with `provider_tx_id IS NULL` are unaffected by the partial unique index.
- Existing `outbox_events` / `inbox_events` tables are additive; rolling back application code leaves existing bookings, payments, tickets, and notification logs intact.
