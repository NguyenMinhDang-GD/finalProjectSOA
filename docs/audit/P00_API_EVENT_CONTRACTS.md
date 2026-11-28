# P00 — API & Event Contract Inventory

## 1. HTTP API Endpoints Inventory

### 1.1 `auth-service` (`:8001`, Gateway: `/api/auth`)
| Method & Path | Auth / Role | Request Schema | Response Schema | Side Effects & Failure Responses | Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /health` | None | - | `{status, service}` | `200` | `services/auth-service/app/main.py:42-44` |
| `GET /metrics` | None | - | Prometheus text | `200` | `services/auth-service/app/metrics.py:27-29` |
| `POST /api/auth/register` | None | `RegisterRequest` (`email`, `password` 6..100, `full_name`, `phone` 8..20) | `AuthTokenResponse` (`201`) | Inserts `CUSTOMER` (bcrypt 10); `409` duplicate email | `services/auth-service/app/routers/auth.py:20-22` |
| `POST /api/auth/login` | None | `LoginRequest` (`email`, `password`) | `AuthTokenResponse` (`200`) | Issues JWT (1440m); `401` bad creds, `403` inactive | `services/auth-service/app/routers/auth.py:25-27` |
| `GET /api/auth/me` | Bearer JWT | - | `UserResponse` (`200`) | `401` invalid JWT, `404` missing user (no `is_active` check) | `services/auth-service/app/routers/auth.py:30-35` |
| `GET /api/auth/users` | JWT + `ADMIN` | - | `list[UserResponse]` | `401`, `403` | `services/auth-service/app/routers/auth.py:38-44` |
| `POST /api/auth/users` | JWT + `ADMIN` | `CreateUserByAdminRequest` | `UserResponse` (`201`) | Creates user with role; `401`, `403`, `409` | `services/auth-service/app/routers/auth.py:47-53` |

### 1.2 `court-booking-service` (`:8002`, Gateway: `/api/branches|locations|courts|pricing-rules|bookings`)
| Method & Path | Auth / Role | Request / Query | Response Schema | Side Effects & Failure Responses | Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /health`, `/metrics` | None | - | JSON / Prometheus | `200` | `main.py:83-85`, `metrics.py:37-39` |
| `GET /api/branches` | None | - | `list[BranchResponse]` | Lists active branches | `routers/courts.py:92-100` |
| `POST /api/branches` | `ADMIN` | `BranchCreateRequest` | `BranchResponse` (`201`) | Auto-increments `branch_number` (race-prone) | `routers/courts.py:103-118` |
| `PATCH /api/branches/{id}` | `ADMIN` | `BranchUpdateRequest` | `BranchResponse` | `404` | `routers/courts.py:121-135` |
| `DELETE /api/branches/{id}` | `ADMIN` | - | `{message}` | Soft/hard delete; `404`, `409` if upcoming bookings | `routers/courts.py:138-180` |
| `GET /api/locations` | None | `?branch_id` | `list[LocationResponse]` | Lists active locations | `routers/courts.py:185-196` |
| `POST/PATCH/DELETE /api/locations` | `ADMIN` | `Location*Request` | `LocationResponse` | `404`, `409` duplicate name or upcoming bookings | `routers/courts.py:199-294` |
| `GET /api/courts` | None | `?include_inactive&branch_id&location_id` | `list[CourtResponse]` | Lists courts | `routers/courts.py:299-322` |
| `GET /api/courts/availability` | None | `?date&branch_id&location_id` | `AvailabilityResponse` | Computes hourly slots 5..21 from PG only | `routers/courts.py:325-333` |
| `POST/PATCH/DELETE /api/courts` | `ADMIN` | `Court*Request` | `CourtResponse` | `404`, `409` | `routers/courts.py:336-441` |
| `GET /api/pricing-rules` | None | - | `list[PricingRuleResponse]` | Lists 8 pricing rules | `routers/courts.py:446-451` |
| `PUT /api/pricing-rules/{id}` | `ADMIN` | `PricingRuleUpdateRequest` | `PricingRuleResponse` | Updates `price_per_hour` (`>0, <=5M`); `404` | `routers/courts.py:454-467` |
| `POST /api/bookings` | Optional JWT | `CreateBookingRequest` | `BookingResponse` (`201`) | Acquires Redis locks (900s), creates `PENDING_PAYMENT` order + `LOCKED` slots; `400`, `404`, `409` | `routers/bookings.py:30-38` |
| `GET /api/bookings/my` | Bearer JWT | - | `list[BookingResponse]` | Filters `user_id == sub` | `routers/bookings.py:41-53` |
| `GET /api/bookings/admin/list` | `ADMIN` or `STAFF` | - | `list[BookingResponse]` | Latest 100 orders | `routers/bookings.py:56-67` |
| `GET /api/bookings/admin/stats` | `ADMIN` | - | `AdminStatsResponse` | Aggregate revenue & counts | `routers/bookings.py:70-75` |
| `POST /api/bookings/admin/{code}/cancel` | `ADMIN` | `CancelBookingRequest` | `BookingResponse` | Cancels any non-cancelled/expired order, publishes `booking.cancelled` | `routers/bookings.py:78-95` |
| `GET /api/bookings/lookup/{code}` | **NONE (IDOR)** | - | `BookingResponse` | **Exposes full customer PII publicly**; `404` | `routers/bookings.py:98-107` |
| `GET /api/bookings/internal/{code}` | `X-Internal-Key` | - | `BookingResponse` | Internal service-to-service lookup; `403`, `404` | `routers/bookings.py:110-123` |
| `POST /api/bookings/{code}/cancel` | **NONE (IDOR)** | `CancelBookingRequest` | `BookingResponse` | **Unauthenticated cancel** of any `PENDING_PAYMENT` booking | `routers/bookings.py:126-146` |

### 1.3 `payment-service` (`:8003`, Gateway: `/api/payments`)
| Method & Path | Auth / Role | Request Schema | Response Schema | Side Effects & Failure Responses | Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /health`, `/metrics` | None | - | JSON / Prometheus | `200` | `main.py:48-50`, `metrics.py:27-29` |
| `POST /api/payments/create` | **NONE** | `CreatePaymentRequest` (`booking_code`) | `PaymentResponse` (`201`) | Fetches booking via internal HTTP, generates VietQR URL; `400`, `404`, `502` | `routers/payments.py:19-21` |
| `GET /api/payments/booking/{code}` | **NONE** | - | `PaymentResponse` | Returns payment tx & VietQR URL; `404` | `routers/payments.py:24-31` |
| `POST /api/payments/webhook` | `X-Webhook-Signature` (HMAC) | `PaymentWebhookRequest` | `PaymentResponse` | Marks `SUCCEEDED`, commits, publishes `payment.succeeded`; `401`, `400` | `routers/payments.py:34-50` |
| `POST /api/payments/simulate-webhook/{code}` | **NONE** (if `ENABLE_DEMO_WEBHOOK=true`) | - | `PaymentResponse` | Marks `SUCCEEDED` without payment or amount check; `403` if disabled | `routers/payments.py:53-63` |

### 1.4 `checkin-qr-service` (`:8004`, Gateway: `/api/checkin`)
| Method & Path | Auth / Role | Request Schema | Response Schema | Side Effects & Failure Responses | Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /health`, `/metrics` | None | - | JSON / Prometheus | `200` | `main.py:53-55`, `metrics.py:27-29` |
| `GET /api/checkin/ticket/{code}` | **NONE (IDOR)** | - | `TicketResponse` | **Exposes customer PII + signed QR payload/image**; `404` | `routers/checkin.py:14-21` |
| `POST /api/checkin/scan` | `STAFF` or `ADMIN` | `ScanQRRequest` (`qr_data`, `bypass_time_check`) | `ScanQRResponse` | Atomic `VALID -> CHECKED_IN`; `400`, `404`, `409` | `routers/checkin.py:24-35` |
| `GET /api/checkin/logs` | `STAFF` or `ADMIN` | - | `list[TicketResponse]` | Latest 100 tickets (without `qr_image_base64`) | `routers/checkin.py:38-43` |

### 1.5 `notification-service` (`:8005`, Gateway: `/api/notifications`)
| Method & Path | Auth / Role | Request Schema | Response Schema | Side Effects & Failure Responses | Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /health`, `/metrics` | None | - | JSON / Prometheus | `200` | `main.py:48-50`, `metrics.py:27-29` |
| `GET /api/notifications/logs` | `STAFF` or `ADMIN` | - | `list[NotificationLogResponse]` | Latest 100 email logs | `routers/notifications.py:13-19` |

---

## 2. RabbitMQ Event Contracts (`pickleball.events`, `TOPIC`, `durable=True`)

| Routing Key | Publisher | Consumer(s) & Queue | Ack / Retry / DLQ | Idempotency & Risk |
| :--- | :--- | :--- | :--- | :--- |
| `booking.expired` | `court-booking-service` | `payment-service` (`payment.booking_events`) | `process(requeue=False)`, **No retry, No DLQ** | Only expires `PENDING` tx. Commit-before-publish risk. |
| `booking.cancelled` | `court-booking-service` | `payment-service` (`payment.booking_events`), `checkin-qr-service` (`checkin.events`) | `process(requeue=False)`, **No retry, No DLQ** | Cancels `PENDING` payment; revokes `VALID` ticket. Commit-before-publish risk. |
| `payment.succeeded` | `payment-service` | `court-booking-service` (`booking.payment_events`), `checkin-qr-service` (`checkin.events`) | `process(requeue=False)`, **No retry, No DLQ** | **Issue:** `checkin-qr-service` issues ticket directly from `payment.succeeded` without waiting for `booking.confirmed` — if booking was expired/conflicted, ticket is still issued! |
| `ticket.issued` | `checkin-qr-service` | `notification-service` (`notification.ticket_email`) | Manual `ack()`, 3x app retry (1.5s, 3.0s), `reject(requeue=False)` -> `pickleball.dlx` / `pickleball.dlq` | Check-then-act `NotificationLog` query (race-prone under concurrency). |

---

## 3. Contract Inconsistencies (Frontend vs Backend)

1. **FastAPI 422 Error Shape (`frontend/src/api/client.ts:38-39`)**: `data.detail` on 422 is an array of objects, causing `[object Object]` to be thrown in `Error` instead of readable validation messages.
2. **Polling `POST /api/payments/create` (`frontend/src/pages/CheckoutPage.tsx:23-28, 53-62`)**: 2.5s polling interval calls `POST /api/payments/create` repeatedly instead of `GET /api/payments/booking/{bookingCode}`.
3. **Unused Admin User Management APIs**: `GET /api/auth/users` and `POST /api/auth/users` exist in `auth-service` but have no UI in `AdminDashboardPage.tsx`.
4. **Client Validation Mismatch**: `RegisterPage.tsx` and `BookingPage.tsx` omit `minLength={2}` on name and `minLength={8}` on phone enforced by backend Pydantic schemas.
5. **Silent Failure in `MyBookingsPage` (`LookupAndHistoryPage.tsx:103-105`)**: Missing `.catch()` causes API errors to look like an empty booking list.
