# B03 — Court Maintenance Scheduling Design

## 1. Domain Model & Serialization
- `MaintenanceBlock` (`maintenance_blocks` table in `booking_db`): `court_id`, `play_date`, `start_hour`, `end_hour`, `reason`, `status` (`SCHEDULED` | `CANCELLED`), `idempotency_key`, `created_by`, `cancelled_by`, `cancelled_at`.
- **RBAC**: Only `ADMIN` can `POST /api/bookings/admin/maintenance` and `POST /api/bookings/admin/maintenance/{id}/cancel`. `STAFF` and `CUSTOMER` can view `GET /api/bookings/maintenance`.

## 2. Redis-Independent PostgreSQL Serialization
Every booking creation, walk-in creation, rescheduling, and maintenance block creation acquires a PostgreSQL row-level `SELECT ... FOR UPDATE` lock on the target `Court` row(s) in deterministic `court_id` order before checking overlaps:
1. `create_booking` checks `MaintenanceBlock` (`status="SCHEDULED"`) overlap before inserting `BookingSlot`.
2. `create_maintenance_block` checks `BookingSlot` (`slot_status IN ('LOCKED', 'BOOKED')`) and existing `MaintenanceBlock` overlap before inserting.
3. Even if Redis is completely unavailable, concurrent maintenance vs booking requests serialize cleanly in PostgreSQL with zero double-booking or maintenance overlap.

## 3. Availability & Audit
- `GET /api/courts/availability?date=YYYY-MM-DD` marks overlapping hours as `status = "MAINTENANCE"`.
- Cancelling a `SCHEDULED` block transitions it to `CANCELLED`, restores `AVAILABLE` status immediately, and records `MAINTENANCE_CANCELLED` in `OperationalAuditLog`.
