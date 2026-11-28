# P00 — Repository Baseline & Runtime Verification Report

**Project:** Pickleball SOA Arena  
**Phase:** P00 (Read-Only Application Audit & Non-Destructive Baseline Verification)  
**Audit Date:** 2026-11-27  

---

## 1. Git Baseline

| Item | Value | Source / Verification Method |
| :--- | :--- | :--- |
| **Current Branch** | `main` | Verified via `.git/HEAD` (`ref: refs/heads/main`) |
| **HEAD Commit Hash** | `6a2866e543769cb7b1dfc21d3b2c03defb4a437e` | Verified via `.git/refs/heads/main` |
| **Working Tree Status** | `UNVERIFIED (BLOCKED)` | `git status` could not execute (`run_command` blocked) |
| **Staged / Unstaged / Untracked Files** | `UNVERIFIED (BLOCKED)` | `git status` could not execute (`run_command` blocked) |
| **Existing Tags** | `UNVERIFIED (BLOCKED)` | `git tag -l` could not execute (`run_command` blocked) |
| **Sensitive Config Ignored (`.gitignore`)** | `.env`, `.env.local`, `tests/`, `docs/` are listed | Verified via `.gitignore` lines 16–26 (`git check-ignore` blocked) |
| **P00-V Re-Verification (2026-11-27)** | HEAD unchanged (`6a2866e543769cb7b1dfc21d3b2c03defb4a437e`) | Terminal & browser still **BLOCKED**; see `P00_V_VERIFICATION.md` |

> [!WARNING]
> **Environment Blocker:** `run_command` failed on every invocation with `exec: "c:\\Users\\Dell\\SOA_Final\\finalProjectSOA\\powershell": executable file not found in %PATH%`. As a result, all CLI-based Git, Docker, Python, and Node/npm commands are recorded as **BLOCKED**. No Git history, working tree, or `.env` file was modified.

---

## 2. Repository Inventory Summary

Because shell directory enumeration was blocked, files were discovered via `docker-compose.yml`, `infra/gateway/nginx.conf`, `infra/grafana/provisioning/`, `frontend/package.json`, and Python/TypeScript module import traversal, then read directly via `read_file`.

| Area | Inspected File Count | Status |
| :--- | :---: | :--- |
| Root (`README.md`, `docker-compose.yml`, `.gitignore`, `.env.example`) | 4 | Inspected |
| `services/auth-service/` | 12 | Inspected (100% of module files) |
| `services/court-booking-service/` | 16 | Inspected (100% of module files) |
| `services/payment-service/` | 12 | Inspected (100% of module files) |
| `services/checkin-qr-service/` | 13 | Inspected (100% of module files) |
| `services/notification-service/` | 12 | Inspected (100% of module files) |
| `frontend/` (config + `src/`) | 22 | Inspected (100% of config & `src/` files) |
| `infra/` (gateway, postgres, prometheus, grafana) | 6 | Inspected |
| `tests/` | 0 | **UNVERIFIED** (probed common filenames via `read_file`; none found, full directory listing blocked by shell failure) |
| **Total Inspected Files** | **97** | **All core source, config, and infra files inspected** |

---

## 3. Baseline Runtime & Build Verification Matrix

| Check | Status | Details / Error |
| :--- | :---: | :--- |
| Docker & Docker Compose availability | **BLOCKED** | `run_command` failed: `powershell` executable not found in `%PATH%` |
| `docker compose config --quiet` | **BLOCKED** | Shell execution unavailable |
| Running containers & healthchecks | **BLOCKED** | Shell execution unavailable |
| API Gateway (`http://localhost:8080/gateway-health`) | **BLOCKED** | Shell & browser inspection unavailable |
| 5 Microservice `/health` endpoints (`8001`–`8005`) | **BLOCKED** | Shell execution unavailable |
| PostgreSQL / Redis / RabbitMQ / Mailpit / Prometheus / Grafana | **BLOCKED** | Shell execution unavailable |
| Frontend live UI inspection (`http://localhost:8080`) | **BLOCKED** | `browser` subagent failed: `DevToolsActivePort` not found at `C:\Users\Dell\AppData\Local\Google\Chrome\User Data\DevToolsActivePort` |
| Frontend `tsc && vite build` | **BLOCKED** | Shell execution unavailable |
| Existing E2E / Unit test suite | **NOT RUN / UNVERIFIED** | No test files found in probed paths; shell execution unavailable |

---

## 4. Proposed Isolated Test Environment for Subsequent Phases (P01+)

Since no automated unit/integration test suite or isolated test database configuration currently exists in the inspected codebase:
1. **Isolated Compose Override (`docker-compose.test.yml`)**: Spin up ephemeral `postgres-test`, `redis-test`, and `rabbitmq-test` (or tmpfs-backed test DBs) on separate ports/networks so tests never touch `pg_data` or existing user data.
2. **Per-Service `pytest` + `httpx.AsyncClient` Suites**: Add `tests/` inside each microservice (or a root `tests/` integration harness) using `pytest-asyncio` with mocked external providers (`payOS`/`SePay`, `SMTP`) and isolated test DB schemas.
3. **Frontend Verification**: Run `npm run build` (`tsc && vite build`) and Playwright/Vitest against the isolated test stack.
