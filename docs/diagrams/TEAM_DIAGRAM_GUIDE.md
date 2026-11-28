# Team Diagram Collaboration Guide

This guide partitions the Version B (`upgrade/soa-complete`) diagramming effort into five independent work packages so team members can prepare academic diagrams in parallel without duplicating effort or mixing Version A (`main`) and Version B (`upgrade/soa-complete`) contracts.

> [!IMPORTANT]
> Check [DIAGRAM_READINESS_TRACKER.md](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/DIAGRAM_READINESS_TRACKER.md) before finalizing any diagram. Only finalize diagrams whose status has transitioned to `READY_TO_DRAW` after remote GitHub publication.

---

## Work Package 1: ERD & Database Architecture
- **Diagram Files:**
  - `docs/diagrams/01-erd/ERD_CONCEPTUAL.puml`
  - `docs/diagrams/01-erd/ERD_AUTH_DB.puml`
  - `docs/diagrams/01-erd/ERD_BOOKING_DB.puml`
  - `docs/diagrams/01-erd/ERD_PAYMENT_DB.puml`
  - `docs/diagrams/01-erd/ERD_CHECKIN_DB.puml`
  - `docs/diagrams/01-erd/ERD_NOTIFICATION_DB.puml`
- **Source of Truth:** [DIAGRAM_SOURCE_OF_TRUTH.md](file:///c:/Users/Dell/SOA_Final/finalProjectSOA/docs/diagrams/DIAGRAM_SOURCE_OF_TRUTH.md) + `services/*/app/models.py` + `main.py` startup DDL.
- **Implementation Dependencies:** B01–B03 schema additions (`booking_reschedule_history`, `maintenance_blocks`, `operational_audit_logs`, `payment_attempts`, `reconciliation_cases`, `refund_transactions`, `financial_audit_logs`, `outbox_events`, `inbox_events`).
- **Priority:** **P1 (High)** — Foundation for all other diagrams.
- **Expected Future Revisions (B04):** `notification_db` (Brevo tracking) and `booking_db` (optional weather metadata). `auth_db`, `payment_db`, and `checkin_db` are expected to remain stable.
- **Recommended Terminology:** Strictly separate **Physical FK** (solid crow's-foot inside `booking_db`) from **Cross-Service Logical Reference** (dashed `<<logical>>` lines). Never draw cross-database physical foreign keys.

## Work Package 2: Use Case & Activity Diagrams
- **Diagram Files:**
  - `docs/diagrams/02-use-case/UC_OVERALL.puml`
  - `docs/diagrams/02-use-case/UC_BY_ACTOR.puml`
  - `docs/diagrams/03-activity/ACT_CUSTOMER_FLOWS.puml`
  - `docs/diagrams/03-activity/ACT_OPERATIONS_FLOWS.puml`
- **Source of Truth:** `frontend/src/App.tsx`, `services/*/app/routers/*.py`, `operations_service.py`, `payment_service.py`.
- **Implementation Dependencies:** B03 RBAC (`Guest`, `CUSTOMER`, `STAFF`, `ADMIN`) and counter/operational workflows.
- **Priority:** **P1 (High)**.
- **Expected Future Revisions (B04):** Use Cases may gain weather alert/notification triggers; existing B03 Activity flows (`ACT_RESCHEDULING`, `ACT_WALKIN_AND_CASH`, `ACT_MAINTENANCE`, `ACT_NO_SHOW_AND_COMPLETE`) are stable.
- **Recommended Terminology:** Use exact actor names (`Guest`, `Customer`, `Staff`, `Admin`) and explicit `<<include>>` / `<<extend>>` stereotypes. Always note Simulated Payment (`MOCK_DEMO` / `SIMULATED_CASH`).

## Work Package 3: Sequence Diagrams
- **Diagram Files:**
  - `docs/diagrams/04-sequence/SEQ_BOOKING_PAYMENT_QR.puml`
  - `docs/diagrams/04-sequence/SEQ_SAGA_AND_COMPENSATION.puml`
  - `docs/diagrams/04-sequence/SEQ_OPERATIONS_B03.puml`
- **Source of Truth:** `services/*/app/routers/*.py`, `services/*/app/services/*.py`, `docs/implementation/B03_EVENT_AND_API_CONTRACTS.md`.
- **Implementation Dependencies:** P01 Outbox/Inbox, B01 locking & guest auth, B02 Saga/refunds, B03 rescheduling/walk-in/maintenance/lifecycle.
- **Priority:** **P2 (Medium-High)**.
- **Expected Future Revisions (B04):** `notification-service` external adapter step (SMTP Mailpit → Brevo API) in `SEQ_BOOKING_PAYMENT_QR` / `SEQ_OPERATIONS_B03`.
- **Recommended Terminology:** Always show synchronous HTTP calls (`-->` / `->`) distinctly from asynchronous Outbox → RabbitMQ → Inbox transitions. Never show an async side effect before the supporting DB commit.

## Work Package 4: Component & Deployment Diagrams
- **Diagram Files:**
  - `docs/diagrams/05-architecture/ARCH_SYSTEM_COMPONENT_DEPLOY.puml`
- **Source of Truth:** `docker-compose.yml`, `docker-compose.prod.yml`, `infra/gateway/nginx.conf`.
- **Implementation Dependencies:** B01 production-like network isolation (`pkb-internal`, `APP_ENV=production`, `VITE_ENABLE_DEMO_CONTROLS=false`).
- **Priority:** **P2 (Medium)**.
- **Expected Future Revisions (B04):** Addition of external Brevo API and Weather API nodes in B04.
- **Recommended Terminology:** Explicitly distinguish Development (`pkb-net`, exposed service ports + Mailpit/Prometheus/Grafana) from Production-like Isolated (`pkb-internal`, only `api-gateway` port exposed).

## Work Package 5: State Machine & Business Lifecycle Diagrams
- **Diagram Files:**
  - `docs/diagrams/05-architecture/ARCH_STATE_MACHINES.puml`
- **Source of Truth:** `booking-service/app/models.py`, `operations_service.py`, `payment-service/app/models.py`, `payment_service.py`.
- **Implementation Dependencies:** B02 financial state machines + B03 `NO_SHOW`, `COMPLETED`, `admission_status`.
- **Priority:** **P1 (High)**.
- **Expected Future Revisions (B04):** Expected to remain **stable**.
- **Recommended Terminology:** Keep `BookingOrder.status` (`PENDING_PAYMENT`, `PAID`, `CANCELLED`, `EXPIRED`, `NO_SHOW`, `COMPLETED`) and `BookingOrder.admission_status` (`NONE`, `ADMITTED`) as separate orthogonal state machines.

---

## Rendering PlantUML Diagrams
1. **VS Code Extension:** Install `jebbs.plantuml`, open any `.puml` file under `docs/diagrams/`, and press `Alt+D` to preview or export PNG/SVG.
2. **CLI (`plantuml.jar`):**
   ```bash
   java -jar plantuml.jar -tpng docs/diagrams/**/*.puml
   ```
   *(Note: Java JDK is installed on this workstation, but `plantuml.jar` is not pre-installed in PATH.)*
