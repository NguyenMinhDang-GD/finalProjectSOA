# B02 Reconciliation, Financial Audit & Observability

## 1. Reconciliation Cases (`reconciliation_cases`)

Automatically opened (`status="OPEN"`) when:
- `UNDERPAYMENT`: `received_amount < expected_amount`
- `OVERPAYMENT`: `received_amount > expected_amount`
- `DUPLICATE_PAYMENT`: distinct `provider_tx_id` received after `SUCCEEDED`
- `LATE_PAYMENT`: payment received after `CANCELLED` / `EXPIRED`
- `CONFIRMATION_FAILED`: booking confirmation saga failure after payment

Admin transitions via `POST /api/payments/admin/reconciliation/{case_id}`: `OPEN` -> `IN_REVIEW` -> `RESOLVED` (with `resolution_action`, `resolution_note`, `resolved_by`, `resolved_at`).

## 2. Financial Audit Log (`financial_audit_logs`)

Immutable append-only records for `PAYMENT`, `REFUND`, and `RECONCILIATION` actions capturing `actor`, `actor_role`, `previous_state`, `new_state`, `amount_vnd`, `reason`, and `metadata_json`.

## 3. Prometheus Metrics (`payment-service`)

- `pickleball_payments_confirmed_total{provider}`
- `pickleball_payments_failed_total{reason}`
- `pickleball_payment_reconciliation_cases_total{case_type}`
- `pickleball_refunds_total{status,policy_tier}`
- `pickleball_payment_compensation_required_total{reason}`
