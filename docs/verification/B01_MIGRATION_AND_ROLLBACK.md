# B01 Migration and Rollback Notes

## 1. Additive Schema Changes
In `services/court-booking-service/app/main.py` (`lifespan`), two nullable columns are added idempotently to `booking_orders`:
- `guest_token_hash VARCHAR(64)`
- `lock_token VARCHAR(64)`

## 2. Legacy Data Compatibility
- Existing users, bookings, payments, QR tickets, P01 Outbox/Inbox records, and compensation records remain untouched.
- Legacy guest bookings (`user_id IS NULL AND guest_token_hash IS NULL`) are **not** silently exposed by booking code alone; they require `STAFF` or `ADMIN` operator-assisted lookup.
- Existing `PKB-YYYYMMDD-XXXX` booking codes remain valid alongside new 40-bit `PKB-YYYYMMDD-XXXXXXXXXX` codes.

## 3. Rollback Considerations
- Rolling back code to `soa-b00-ui-release` leaves the nullable `guest_token_hash` and `lock_token` columns harmlessly unused in PostgreSQL; no destructive `DROP COLUMN` is required.
