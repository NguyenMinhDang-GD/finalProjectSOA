# Agent Guardrails — Pickleball SOA Arena

These non-negotiable rules govern **all phases (P00 and subsequent implementation phases)** unless explicitly overridden by the project owner:

1. **Never rewrite the application from scratch.**
2. **Preserve all five existing microservices:**
   - `auth-service`
   - `court-booking-service`
   - `payment-service`
   - `checkin-qr-service`
   - `notification-service`
3. **Preserve the technology stack:** React, TypeScript, FastAPI, PostgreSQL, Redis, RabbitMQ, Nginx, Prometheus, and Grafana.
4. **Never modify unrelated files** outside the authorized phase scope.
5. **Never delete database records, Docker volumes, existing user data, or Git history.**
6. **Never execute destructive commands** such as `git reset --hard`, `git clean -fd`, `docker compose down -v`, or destructive database migrations.
7. **Never push changes to remote repositories** without explicit permission.
8. **Never overwrite an existing `.env` file.**
9. **Never expose secrets**, API keys, JWT secrets, passwords, bank account credentials, or access tokens in reports or committed files.
10. **Never replace actual business logic with hardcoded responses.**
11. **Never fabricate** successful API responses, payment confirmations, test results, screenshots, or logs.
12. **Never claim PASS** when a verification step was not actually executed.
13. **Clearly distinguish** `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`, and `NOT APPLICABLE`.
14. **Never silently disable** validation, authorization, concurrency protection, or security controls to make tests pass.
15. **Do not introduce unnecessary** frameworks, dependencies, microservices, or infrastructure.
16. **Do not perform major dependency upgrades** without explicit approval.
17. **Never initiate actual financial transactions, refunds, or external notifications** without explicit permission.
18. **Preserve existing working functionality and backward compatibility** wherever reasonably possible.
19. **Report every changed file and its purpose.**
20. **Stop after completing the current phase.** Never automatically proceed to the next phase.
