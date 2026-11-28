from pydantic_settings import BaseSettings

_INSECURE_DEFAULTS = {
    "",
    "soa-pickleball-jwt-super-secret-key-2026",
    "soa-pickleball-internal-service-key-2026",
    "soa-pickleball-webhook-hmac-secret-2026",
    "soa-pickleball-qr-hmac-secret-key-2026",
    "change-in-production",
}


class Settings(BaseSettings):
    service_name: str = "payment-service"
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://pickleball:pickleball_secret@localhost:5432/payment_db"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    booking_service_url: str = "http://court-booking-service:8002"
    auth_service_url: str = "http://auth-service:8001"
    jwt_secret: str = "soa-pickleball-jwt-super-secret-key-2026"
    jwt_algorithm: str = "HS256"
    internal_api_key: str = "soa-pickleball-internal-service-key-2026"
    webhook_secret: str = "soa-pickleball-webhook-hmac-secret-2026"
    vietqr_bank_bin: str = "SIMULATED"
    vietqr_account_no: str = "DEMO-ONLY"
    vietqr_account_name: str = "THANH TOAN GIA LAP"
    payment_mode: str = "MOCK_DEMO"  # MOCK_DEMO | MOCK_TEST | DISABLED
    enable_demo_webhook: bool = True
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173"

    @property
    def normalized_payment_mode(self) -> str:
        mode = (self.payment_mode or "MOCK_DEMO").strip().upper()
        if mode not in ("MOCK_DEMO", "MOCK_TEST", "DISABLED"):
            return "DISABLED"
        return mode

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip() and o.strip() != "*"]

    @property
    def is_demo_webhook_enabled(self) -> bool:
        return (
            self.enable_demo_webhook
            and self.app_env.lower() != "production"
            and self.normalized_payment_mode in ("MOCK_DEMO", "MOCK_TEST")
        )

    @property
    def is_payment_simulation_enabled(self) -> bool:
        return self.normalized_payment_mode in ("MOCK_DEMO", "MOCK_TEST")

    def validate_production_settings(self) -> None:
        if self.app_env.lower() != "production":
            return
        for name, val in (
            ("JWT_SECRET", self.jwt_secret),
            ("INTERNAL_API_KEY", self.internal_api_key),
            ("WEBHOOK_SECRET", self.webhook_secret),
        ):
            if not val or len(val.strip()) < 24 or val.strip() in _INSECURE_DEFAULTS:
                raise RuntimeError(f"Unsafe or missing {name} in production mode")


settings = Settings()
