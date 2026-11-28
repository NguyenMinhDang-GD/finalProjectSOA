# P01 — Acceptance Test Results

**Test Environment:** Isolated Docker Compose project `pkb-test` (`docker-compose.test.yml`) with dedicated PostgreSQL (`15432`), Redis (`16379`), RabbitMQ (`15673`/`25672`), Mailpit (`11025`/`18025`), and Gateway (`18080`). Zero shared volumes or databases with the main stack.

## 1. Execution Results (`T01`–`T15`)

| Test | Command | Exit Code | Status | Observed Evidence |
| :--- | :--- | :---: | :---: | :--- |
| **T01** | `python tests/test_p01_reliability.py` | `0` | **PASS** | Happy path `PKB-20261129-DCAB`: booking `PAID`, ticket `VALID`, Mailpit `SENT=1`, outbox `PUBLISHED` in all 3 producers |
| **T02** | `python tests/test_p01_reliability.py` | `0` | **PASS** | 3x duplicate webhooks -> 1 `SUCCEEDED` payment, 1 `booking.confirmed`, 1 `VALID` ticket |
| **T03** | `python tests/test_p01_reliability.py` | `0` | **PASS** | 5 concurrent webhooks -> 1 `SUCCEEDED` payment, 1 `booking.confirmed`, 1 `VALID` ticket (`PKB-20261129-74BF`) |
| **T04** | `python tests/test_p01_reliability.py` | `0` | **PASS** | 2x duplicate `booking.confirmed` -> 1 ticket, 1 `ticket.issued` outbox |
| **T05** | `python tests/test_p01_reliability.py` | `0` | **PASS** | Cancelled booking `PKB-20261129-9946` + webhook -> booking stayed `CANCELLED`, `booking_compensations` & `payment_compensations` = `COMPENSATION_REQUIRED`, 0 tickets |
| **T06** | `python tests/test_p01_reliability.py` | `0` | **PASS** | Stopped `rabbitmq-test`, paid `PKB-20261129-858D` (`outbox_events=PENDING`), started `rabbitmq-test` -> recovered to `PUBLISHED`, `PAID`, `VALID` |
| **T07** | `python tests/test_p01_reliability.py` | `0` | **PASS** | Stopped `rabbitmq-test`, paid `PKB-20261129-7930`, restarted `payment-service`, started `rabbitmq-test` -> recovered to `VALID` |
| **T08** | `python tests/test_p01_reliability.py` | `0` | **PASS** | Replayed `payment.succeeded` for `PKB-20261129-DCAB` -> skipped by `inbox_events`, still 1 `booking.confirmed` |
| **T09** | `python tests/test_p01_reliability.py` | `0` | **PASS** | Paused/unpaused `postgres-test` -> transient failure recovered cleanly (`PKB-20261129-768E`) |
| **T10** | `python tests/test_p01_reliability.py` | `0` | **PASS** | 3 malformed/invalid events routed to `pickleball.dlq` (`0 -> 3`) |
| **T11** | `python tests/test_p01_reliability.py` | `0` | **PASS** | Expired booking `PKB-20261129-B771` + webhook -> `reconciliation_status=COMPENSATION_REQUIRED`, `booking=EXPIRED`, 0 tickets |
| **T12** | `python tests/test_p01_reliability.py` | `0` | **PASS** | Admin cancel revoked ticket (`REVOKED`), delayed `booking.confirmed` did not reactivate, scan returned `400` |
| **T13** | `python tests/test_p01_reliability.py` | `0` | **PASS** | 5 concurrent `/api/checkin/scan` -> `1x 200`, `4x 409 Conflict` |
| **T14** | `python tests/test_p01_reliability.py` | `0` | **PASS** | 2 concurrent `dispatch_pending_outbox_once()` workers claimed & published `10/10` (`dispatched=10+0`) |
| **T15** | `docker compose config --quiet; docker compose build ...; docker build ./frontend; docker compose ps` | `0` | **PASS** | Main Compose valid, all 4 modified backend images + frontend `tsc && vite build` succeeded, all 13 main containers healthy & untouched |

## 2. Reproduction Command

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-p01.ps1
```
