# B03-DOC — Architectural Diagram Source of Truth & Traceability

**Branch:** `upgrade/soa-complete`
**Accepted B03 Implementation Baseline Commit:** `ddb64f9cc31e2e32e152ddb6ce44b20ab1ee5ab3` (`soa-b03-checkpoint`)
**Scope:** Read-only source extraction from all five microservices, PostgreSQL initialization, Docker Compose topologies, and React frontend routes. No future B04 features (e.g., Brevo or weather integration) are included.

---

## 1. Git & PlantUML Verification Notes

### Protected References
- `main`: `e616aa8294cf54486e05c81366ff8a3f5fb290f1`
- `soa-b02-checkpoint`:
  - `git cat-file -t soa-b02-checkpoint` → `tag` (an **annotated tag object**)
  - `git rev-parse soa-b02-checkpoint` → `91fc0ff6deffa9b61efd0ce339f48eb7acbb9d3d` (annotated tag object SHA)
  - `git rev-parse "soa-b02-checkpoint^{commit}"` → `219531abeff4bd78adee175861c67859804b6c08` (dereferenced target commit SHA)
- `soa-b03-checkpoint`: `ddb64f9cc31e2e32e152ddb6ce44b20ab1ee5ab3`

### PlantUML Syntax & Rendering Verification Status
- Validated and rendered locally with **PlantUML `v1.2024.8`**, **Java `26.0.2.1`**, and **Graphviz `2.44.1`**:
  - `java -jar plantuml-1.2024.8.jar -checkonly` → `CHECKONLY_EXIT=0` (15 files, 0 syntax errors)
  - `java -jar plantuml-1.2024.8.jar -tsvg` → `RENDER_EXIT=0` (**39/39 diagram blocks rendered**, 0 failed).

---

## 2. Physical Foreign Keys vs Cross-Service Logical References

- **Physical FKs** exist **only** inside `booking_db`:
  - `locations.branch_id` → `branches.id`
  - `courts.location_id` → `locations.id`
  - `booking_orders.court_id` → `courts.id`
  - `booking_slots.booking_id` → `booking_orders.id` (`ON DELETE CASCADE`)
  - `booking_slots.court_id` → `courts.id`
  - `maintenance_blocks.court_id` → `courts.id`
- **Intra-DB Logical References (no DB FK)** exist in `booking_db` (`booking_reschedule_history.booking_id`, `booking_compensations.booking_code`, `operational_audit_logs.entity_id`) and `payment_db` (`payment_attempts.payment_id`, `reconciliation_cases.payment_id`, `refund_transactions.payment_id`, `payment_compensations.payment_id`, `financial_audit_logs.booking_code`).
- **Cross-Service Logical References (dashed in ERDs)**:
  - `booking_db.booking_orders.user_id` → `auth_db.users.id`
  - `payment_db.payment_transactions.(booking_id, booking_code)` → `booking_db.booking_orders.(id, booking_code)`
  - `payment_db.refund_transactions.booking_id` → `booking_db.booking_orders.id`
  - `checkin_db.checkin_tickets.(booking_id, booking_code)` → `booking_db.booking_orders.(id, booking_code)`
  - `checkin_db.cancelled_bookings.booking_code` → `booking_db.booking_orders.booking_code`
  - `notification_db.notification_logs.booking_code` → `booking_db.booking_orders.booking_code`

---

## 3. Diagram Index & Traceability Matrix

| Diagram File / Block | Purpose | Source Files Inspected | Key Classes / Functions | Relevant API Routes / Events | Limitations & B04 Stability |
|---|---|---|---|---|---|
| [ERD_CONCEPTUAL.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/01-erd/ERD_CONCEPTUAL.puml) | Cross-DB conceptual ERD separating physical FKs from logical refs | `infra/postgres/init-multi-db.sql`, all 5 `app/models.py` | `User`, `BookingOrder`, `PaymentTransaction`, `CheckinTicket`, `NotificationLog` | All 5 DBs (`auth_db`, `booking_db`, `payment_db`, `checkin_db`, `notification_db`) | **May update in B04** if weather/email metadata tables are added |
| [ERD_AUTH_DB.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/01-erd/ERD_AUTH_DB.puml) | Exact `auth_db` schema | `services/auth-service/app/models.py`, `main.py` | `User` | `/api/auth/*` | **Stable** |
| [ERD_BOOKING_DB.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/01-erd/ERD_BOOKING_DB.puml) | Exact `booking_db` schema + partial unique index `uq_active_court_slot` | `services/court-booking-service/app/models.py`, `main.py` | `Branch`, `Location`, `Court`, `PricingRule`, `BookingOrder`, `BookingSlot`, `BookingRescheduleHistory`, `MaintenanceBlock`, `OperationalAuditLog`, `BookingCompensation`, `OutboxEvent`, `InboxEvent` | `/api/branches`, `/api/locations`, `/api/courts`, `/api/pricing-rules`, `/api/bookings/*` | **May update in B04** if weather alerts attach to bookings/courts |
| [ERD_PAYMENT_DB.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/01-erd/ERD_PAYMENT_DB.puml) | Exact `payment_db` schema + partial unique index `uq_payment_provider_tx_id` | `services/payment-service/app/models.py`, `main.py` | `PaymentTransaction`, `PaymentAttempt`, `ReconciliationCase`, `RefundTransaction`, `FinancialAuditLog`, `PaymentCompensation`, `OutboxEvent`, `InboxEvent` | `/api/payments/*` | **Stable** (simulated-only scope locked) |
| [ERD_CHECKIN_DB.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/01-erd/ERD_CHECKIN_DB.puml) | Exact `checkin_db` schema | `services/checkin-qr-service/app/models.py`, `main.py` | `CheckinTicket`, `CancelledBooking`, `OutboxEvent`, `InboxEvent` | `/api/checkin/*` | **Stable** |
| [ERD_NOTIFICATION_DB.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/01-erd/ERD_NOTIFICATION_DB.puml) | Exact `notification_db` schema (legacy `uq_notification_sent_booking` dropped) | `services/notification-service/app/models.py`, `main.py` | `NotificationLog`, `InboxEvent` | `/api/notifications/logs` | **May update in B04** for Brevo delivery status tracking |
| [UC_OVERALL.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/02-use-case/UC_OVERALL.puml) & [UC_BY_ACTOR.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/02-use-case/UC_BY_ACTOR.puml) | Actors (Guest, Customer, Staff, Admin), associations, `<<include>>`, `<<extend>>` | `frontend/src/App.tsx`, all `app/routers/*.py` | `require_roles`, `get_current_claims`, `get_optional_claims` | All public, customer, staff, admin routes | **May update in B04** for weather notifications/alerts |
| [ACT_CUSTOMER_FLOWS.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/03-activity/ACT_CUSTOMER_FLOWS.puml) | Registration/Login, Booking, Simulated Payment, Lookup, Rescheduling, Cancel/Refund | `auth_service.py`, `booking_service.py`, `operations_service.py`, `payment_service.py` | `create_booking`, `reschedule_booking`, `cancel_booking`, `confirm_payment_idempotent` | `/api/auth/*`, `/api/bookings/*`, `/api/payments/*` | **Stable** |
| [ACT_OPERATIONS_FLOWS.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/03-activity/ACT_OPERATIONS_FLOWS.puml) | QR Check-in, Walk-in & Cash, Maintenance, No-Show, Completion, Reconciliation | `checkin_service.py`, `operations_service.py`, `payment_service.py` | `scan_and_checkin`, `collect_cash_at_counter`, `create_maintenance_block`, `mark_booking_no_show`, `complete_booking`, `update_reconciliation_case` | `/api/checkin/scan`, `/api/bookings/staff/*`, `/api/bookings/admin/maintenance*`, `/api/payments/staff/cash-collect`, `/api/payments/admin/reconciliation/*` | **Stable** |
| [SEQ_BOOKING_PAYMENT_QR.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/04-sequence/SEQ_BOOKING_PAYMENT_QR.puml) | Auth, Booking Creation, Simulated Payment Confirmation, QR Issuance, Check-in Claim | `auth.py`, `bookings.py`, `payments.py`, `checkin.py`, `email_service.py` | `enqueue_outbox_event`, `start_payment_consumer`, `start_consumers`, `scan_and_checkin` | `payment.succeeded`, `booking.confirmed`, `ticket.issued` | **Stable** (Mailpit SMTP in dev; Brevo planned in B04) |
| [SEQ_SAGA_AND_COMPENSATION.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/04-sequence/SEQ_SAGA_AND_COMPENSATION.puml) | Cancellation & Simulated Refund Saga; Late Payment Compensation | `bookings.py`, `payment_service.py`, `checkin_service.py` | `cancel_booking`, `_create_reconciliation_case`, `execute_refund` | `booking.cancelled`, `refund.succeeded`, `payment.compensation_required` | **Stable** |
| [SEQ_OPERATIONS_B03.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/04-sequence/SEQ_OPERATIONS_B03.puml) | Rescheduling & QR Versioning, Walk-in & Cash, Maintenance Concurrency, No-Show & Complete | `operations_service.py`, `payment_service.py`, `checkin_service.py` | `reschedule_booking`, `collect_cash_at_counter`, `create_maintenance_block`, `mark_booking_no_show`, `complete_booking` | `booking.rescheduled`, `booking.no_show`, `booking.completed`, `court.maintenance_scheduled` | **Stable** |
| [ARCH_SYSTEM_COMPONENT_DEPLOY.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/05-architecture/ARCH_SYSTEM_COMPONENT_DEPLOY.puml) | System Context, Component Diagram, Dev vs Prod Deployment | `docker-compose.yml`, `docker-compose.prod.yml`, `infra/gateway/nginx.conf` | Nginx gateway, 5 FastAPI services, Postgres/Redis/RabbitMQ/Mailpit | `pkb-net` (Dev) vs `pkb-internal` (Prod-like, `VITE_ENABLE_DEMO_CONTROLS=false`) | **May update in B04** with external Brevo & weather adapters |
| [ARCH_STATE_MACHINES.puml](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/05-architecture/ARCH_STATE_MACHINES.puml) | State machines for Booking, Admission, Payment, Refund, Reconciliation | `booking-service/models.py`, `payment-service/models.py`, `operations_service.py`, `payment_service.py` | `BookingOrder`, `PaymentTransaction`, `RefundTransaction`, `ReconciliationCase` | Status transitions enforced under `SELECT ... FOR UPDATE` | **Stable** |
