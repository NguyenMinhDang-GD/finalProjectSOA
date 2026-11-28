# B00 — Database Migration Verification (`B00-T08` / `B00-T09`)

## 1. Isolated Upgrade Procedure
1. Created isolated Compose project `pkb-mig-test` with dedicated volume `pkb_mig_pg` from `main` (`bfa1535`) via temporary `git worktree`.
2. Seeded representative legacy records: `3` users, `2` bookings (`1 PAID`, `1 PENDING_PAYMENT`), `2` payments (`1 SUCCEEDED`, `1 PENDING`), `1` QR ticket (`VALID`), `1` notification log (`SENT`).
3. Upgraded `pkb-mig-test` to `upgrade/soa-complete` against the **same** `pkb_mig_pg` volume.

## 2. Observed Results
- **Pre-Upgrade Counts:** `{"emails":"1","users":"3","bookings":"2","tickets":"1","payments":"2"}`
- **Post-Upgrade Counts:** `{"emails":"1","users":"3","bookings":"2","tickets":"1","payments":"2"}` (100% preserved)
- **New Structures Verified:**
  - `booking_db` tables: `outbox_events`, `inbox_events`, `booking_compensations`
  - `payment_db` columns & index: `reconciliation_status`, `reconciliation_note`, `uq_payment_provider_tx_id`
- **Post-Restart (`B00-T09`):** `POST_RESTART_BOOKINGS: 2` — repeatable and non-destructive.
