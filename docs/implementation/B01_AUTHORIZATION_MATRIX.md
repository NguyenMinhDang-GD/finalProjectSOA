# B01 Authorization Matrix

| Resource / Action | Anonymous | Guest (`X-Guest-Token`) | Customer (`CUSTOMER`) | Staff (`STAFF`) | Admin (`ADMIN`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `GET /api/branches`, `/locations`, `/courts`, `/courts/availability`, `/pricing-rules` | Allow | Allow | Allow | Allow | Allow |
| `POST /api/bookings` (Create booking) | Allow (issues guest token) | Allow | Allow (bound to `user_id`) | Allow | Allow |
| `GET /api/bookings/my` | `401` | `401` | Own only | Own only | Own only |
| `GET /api/bookings/lookup/{code}` | `401` | Matching booking only | Own only | Allow | Allow |
| `POST /api/bookings/{code}/cancel` | `401` | Matching booking (`PENDING_PAYMENT`) | Own (`PENDING_PAYMENT`) | `403` | `403` (use `/admin/{code}/cancel`) |
| `POST /api/payments/create`, `GET /api/payments/booking/{code}` | `401` | Matching booking only | Own only | Allow | Allow |
| `POST /api/payments/simulate-webhook/{code}` | `403` | `403` | `403` | Allow (non-prod only) | Allow (non-prod only) |
| `POST /api/payments/webhook` | HMAC-SHA256 | HMAC-SHA256 | HMAC-SHA256 | HMAC-SHA256 | HMAC-SHA256 |
| `GET /api/checkin/ticket/{code}` | `401` | Matching booking only | Own only | Allow | Allow |
| `POST /api/checkin/scan`, `GET /api/checkin/logs` | `401` | `401` | `403` | Allow | Allow |
| `POST /api/bookings/admin/*`, `GET /api/bookings/admin/stats`, `GET/POST /api/auth/users` | `401` | `401` | `403` | `403` | Allow |
| `GET /api/bookings/internal/*`, `POST /api/bookings/internal/*/authorize` | Gateway `403` | Gateway `403` | Gateway `403` | Gateway `403` | Gateway `403` (`X-Internal-Key` only) |
