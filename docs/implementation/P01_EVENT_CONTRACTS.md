# P01 — Event Contracts & RabbitMQ Topology

## 1. Exchange & Dead-Letter Topology

- **Main Exchange:** `pickleball.events` (`topic`, `durable=True`)
- **Dead-Letter Exchange:** `pickleball.dlx` (`fanout`, `durable=True`)
- **Dead-Letter Queue:** `pickleball.dlq` (`durable=True`, bound to `pickleball.dlx`)

## 2. Versioned Queues & Bindings

| Queue Name | Service | Bindings | DLX | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `booking.payment_events.v2` | `court-booking-service` | `payment.succeeded` | `pickleball.dlx` | Replaces non-DLX `booking.payment_events` without deleting legacy queue |
| `payment.booking_events.v2` | `payment-service` | `booking.expired`, `booking.cancelled`, `booking.confirmation_failed` | `pickleball.dlx` | Replaces non-DLX `payment.booking_events` |
| `checkin.events.v2` | `checkin-qr-service` | `booking.confirmed`, `booking.cancelled` | `pickleball.dlx` | Replaces `checkin.events`; **no longer bound to `payment.succeeded`** |
| `notification.ticket_email` | `notification-service` | `ticket.issued` | `pickleball.dlx` | Existing queue preserved |

## 3. Standard Event Envelope (`schema_version: 1`)

Every outbox-published event includes:
- `event`: string (routing key)
- `event_id`: UUID string (unique per outbox row)
- `schema_version`: `1`
- `correlation_id`: UUID string propagated across the saga
- `causation_id`: UUID string of the triggering event (when triggered by a consumer)

### Legacy Event Compatibility
Messages lacking `event_id` receive a deterministic SHA-256 fallback ID (`legacy:<32-hex>`) derived from `(event_type, booking_code, payment_id/ticket_id)` so retries never generate a new random ID.

## 4. Event Catalog

| Event Type | Publisher | Consumers | Purpose |
| :--- | :--- | :--- | :--- |
| `payment.succeeded` | `payment-service` | `court-booking-service` | Signals funds captured for a `PENDING` payment |
| `payment.compensation_required` | `payment-service` | *(audit / future P05)* | Late webhook funds received for `EXPIRED`/`CANCELLED` tx |
| `booking.confirmed` | `court-booking-service` | `checkin-qr-service` | Authorizes QR ticket issuance after atomic `PAID`/`BOOKED` commit |
| `booking.confirmation_failed` | `court-booking-service` | `payment-service` | Signals payment received for non-confirmable booking (`COMPENSATION_REQUIRED`) |
| `booking.expired` | `court-booking-service` | `payment-service` | Releases unpaid expired reservation |
| `booking.cancelled` | `court-booking-service` | `payment-service`, `checkin-qr-service` | Cancels unpaid/paid booking and revokes `VALID` ticket |
| `ticket.issued` | `checkin-qr-service` | `notification-service` | Triggers QR ticket email delivery |
