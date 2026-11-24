from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "payment-service"
    database_url: str = "postgresql+asyncpg://pickleball:pickleball_secret@localhost:5432/payment_db"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    booking_service_url: str = "http://court-booking-service:8002"
    internal_api_key: str = "soa-pickleball-internal-service-key-2026"
    webhook_secret: str = "soa-pickleball-webhook-hmac-secret-2026"
    vietqr_bank_bin: str = "970422"
    vietqr_account_no: str = "0123456789"
    vietqr_account_name: str = "SAN PICKLEBALL SOA"
    enable_demo_webhook: bool = True


settings = Settings()
