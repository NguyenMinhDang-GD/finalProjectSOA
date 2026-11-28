# Diagram Changelog & Future Impact Convention

## Purpose
This changelog tracks structural, behavioral, and contract changes across phases on `upgrade/soa-complete` so team members only update affected diagrams instead of redrawing the entire system.

---

## Baseline: B03 (v1.0-b03-verified)
- **Target Branch:** `upgrade/soa-complete`
- **Accepted B03 Baseline Commit:** `ddb64f9cc31e2e32e152ddb6ce44b20ab1ee5ab3` (`soa-b03-checkpoint`)
- **Added Diagrams:**
  - `01-erd/ERD_CONCEPTUAL.puml`, `ERD_AUTH_DB.puml`, `ERD_BOOKING_DB.puml`, `ERD_PAYMENT_DB.puml`, `ERD_CHECKIN_DB.puml`, `ERD_NOTIFICATION_DB.puml`
  - `02-use-case/UC_OVERALL.puml`, `UC_BY_ACTOR.puml`
  - `03-activity/ACT_CUSTOMER_FLOWS.puml`, `ACT_OPERATIONS_FLOWS.puml`
  - `04-sequence/SEQ_BOOKING_PAYMENT_QR.puml`, `SEQ_SAGA_AND_COMPENSATION.puml`, `SEQ_OPERATIONS_B03.puml`
  - `05-architecture/ARCH_SYSTEM_COMPONENT_DEPLOY.puml`, `ARCH_STATE_MACHINES.puml`
- **Key Entities & Attributes Established:**
  - `booking_orders` extended with `booking_source`, `booking_revision`, `no_show_at`, `no_show_by`, `completed_at`, `completed_by`.
  - New `booking_db` tables: `booking_reschedule_history`, `maintenance_blocks`, `operational_audit_logs`.
  - `payment_transactions` extended with `payment_method`, `booking_revision`, `collected_by`, `collected_at`.
  - `checkin_tickets` extended with `booking_revision`; `notification_logs` dropped `uq_notification_sent_booking`.
- **Key Workflows, APIs & Events:**
  - Rescheduling (`/reschedule-quote`, `/reschedule`, `/reschedule-history`, `booking.rescheduled`)
  - Walk-in & Simulated Counter Cash (`/staff/walk-in`, `/staff/cash-collect`)
  - Court Maintenance (`/maintenance`, `/admin/maintenance`, `/admin/maintenance/{id}/cancel`, `court.maintenance_scheduled`, `court.maintenance_cancelled`)
  - Operational Lifecycle (`/staff/{code}/no-show`, `/staff/{code}/complete`, `booking.no_show`, `booking.completed`)

---

## Standard Template for Future Phases (e.g., B04)

```markdown
## Phase: <PHASE_ID> (<REVISION_TAG>)
- **Target Branch / Commit:** `upgrade/soa-complete` @ `<commit-sha>`
- **Added Diagrams:** ...
- **Modified Diagrams:** ...
- **Unaffected Diagrams:** ...
- **Changed Entities & Attributes:** ...
- **Changed Relationships:** ...
- **Changed Business Workflows:** ...
- **Changed API Contracts:** ...
- **Changed Event Contracts:** ...
```
