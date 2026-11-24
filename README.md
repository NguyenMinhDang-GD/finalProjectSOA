# Pickleball SOA Arena — Hệ thống Quản lý & Đặt sân Pickleball (Microservices)

Đồ án cuối kỳ môn **Kiến trúc Hướng dịch vụ (SOA)** xây dựng hệ thống quản lý và đặt sân bóng Pickleball theo kiến trúc **Microservices**, đáp ứng trọn vẹn luồng nghiệp vụ thực tế:

> **Truy cập Web → (Tùy chọn) Đăng nhập → Chọn sân & khung giờ → Giữ chỗ tạm thời (15 phút) → Chuyển khoản VietQR → Nhận vé QR ký số qua Email → Nhân viên quét QR Check-in tại sân**

---

## 1. Kiến trúc & Công nghệ sử dụng

- **Backend (5 Python FastAPI Microservices độc lập):** `Python 3.12`, `FastAPI`, `Pydantic v2`, `SQLAlchemy 2.0 (asyncpg)`, `Redis`, `aio-pika (RabbitMQ)`, `prometheus-client`, `bcrypt`, `PyJWT`.
- **Frontend:** `React 18`, `Vite`, `TypeScript`, `Tailwind CSS`, `html5-qrcode` (quét QR trực tiếp bằng Camera trình duyệt), `lucide-react`.
- **Hạ tầng & Giám sát:** `Nginx` (API Gateway), `PostgreSQL 16` (**Database-per-Service**: 5 database tách biệt), `Redis 7` (Distributed Slot Lock), `RabbitMQ 3.13` (Topic Exchange + Dead-Letter Queue), `Mailpit` (SMTP Demo Server), `Prometheus`, `Grafana` (Auto-provisioned Dashboard), `ngrok` (Public HTTPS Tunnel).

### Danh sách các Service
| Thành phần | Port | Database | Chức năng chính |
| :--- | :---: | :--- | :--- |
| **API Gateway (`Nginx`)** | `8080` | - | Điểm truy cập duy nhất (`/` Frontend, `/api/*` Microservices). |
| **`auth-service`** | `8001` | `auth_db` | Đăng ký, đăng nhập, `bcrypt`, cấp JWT & phân quyền RBAC (`CUSTOMER`, `STAFF`, `ADMIN`). |
| **`court-booking-service`** | `8002` | `booking_db` + `Redis` | Quản lý sân/bảng giá (thường/cao điểm/cuối tuần), chặn đặt giờ quá khứ, khóa slot 15p (`Redis NX` + `PG Partial Unique Index`), Worker nhả sân quá hạn. |
| **`payment-service`** | `8003` | `payment_db` | Sinh mã **VietQR**, xử lý Webhook HMAC idempotent, nút giả lập Demo Webhook, phát sự kiện `payment.succeeded`. |
| **`checkin-qr-service`** | `8004` | `checkin_db` | Sinh vé QR ký số `HMAC-SHA256`, kiểm tra khung giờ (cho phép vào sớm 30p), cập nhật nguyên tử chống quét lại 2 lần. |
| **`notification-service`** | `8005` | `notification_db` | Consumer RabbitMQ gửi Email HTML đính kèm ảnh QR (`aiosmtplib`), Retry 3 lần + DLQ (`pickleball.dlq`). |

---

## 2. Yêu cầu môi trường
- **Docker Desktop** (đang chạy cùng Docker Compose v2).
- **Python 3.12+** (nếu muốn chạy script kiểm thử E2E trên máy host).

---

## 3. Hướng dẫn Khởi chạy nhanh

### Bước 1: Chuẩn bị file cấu hình `.env`
Nếu chưa có file `.env`, sao chép từ file mẫu:
```powershell
Copy-Item .env.example .env
```
*(Mặc định `.env` đã cấu hình sẵn để chạy ngay với PostgreSQL, Redis, RabbitMQ và hộp thư test Mailpit; nếu muốn gửi tới Gmail thật, cập nhật các biến `SMTP_*` trong `.env`).*

### Bước 2: Build và khởi chạy toàn bộ hệ thống
```powershell
docker compose up -d --build
```
Kiểm tra trạng thái các container:
```powershell
docker compose ps
```

### Bước 3: Truy cập các giao diện
- **Web App (Đặt sân / Quét QR / Admin):** http://localhost:8080
- **Hộp thư Email Demo (Mailpit):** http://localhost:8025
- **Grafana Dashboard (`admin` / `admin`):** http://localhost:3100 *(chọn `SOA Monitoring → Pickleball SOA Overview`)*
- **Prometheus Targets:** http://localhost:9090/targets
- **RabbitMQ Management (`guest` / `guest`):** http://localhost:15672
- **Swagger OpenAPI từng Service:**
  - Auth: http://localhost:8080/api/auth/docs
  - Booking: http://localhost:8080/api/bookings/docs
  - Payment: http://localhost:8080/api/payments/docs
  - Check-in QR: http://localhost:8080/api/checkin/docs
  - Notification: http://localhost:8080/api/notifications/docs

---

## 4. Tài khoản Demo mặc định
| Vai trò | Email | Mật khẩu |
| :--- | :--- | :--- |
| **Admin (Chủ sân)** | `admin@pickleball.vn` | `Admin@123` |
| **Staff (Nhân viên quét QR)** | `staff@pickleball.vn` | `Staff@123` |
| **Customer (Khách hàng)** | `khachhang@pickleball.vn` | `Customer@123` |

*(Khách hàng cũng có thể đặt sân nhanh mà không cần đăng nhập).*

---

## 5. Public ra Internet qua Ngrok (HTTPS)
1. Lấy Authtoken tại https://dashboard.ngrok.com và điền vào `NGROK_AUTHTOKEN=...` trong `.env`.
2. Khởi chạy thêm container `ngrok`:
   ```powershell
   docker compose --profile tunnel up -d ngrok
   ```
3. Mở http://localhost:4040 để lấy link `https://xxxx.ngrok-free.app` (dùng link HTTPS này trên điện thoại 4G để mở Camera quét QR tại `/staff/scanner`).

---

## 6. Vận hành & Theo dõi Log
Xem log trực tiếp của các microservices:
```powershell
docker compose logs -f
```

Dừng hệ thống khi không sử dụng:
```powershell
docker compose down
```
