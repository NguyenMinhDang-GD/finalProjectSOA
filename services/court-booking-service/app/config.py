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
    service_name: str = "court-booking-service"
    app_env: str = "development"  # development | test | production
    database_url: str = "postgresql+asyncpg://pickleball:pickleball_secret@localhost:5432/booking_db"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_secret: str = "soa-pickleball-jwt-super-secret-key-2026"
    jwt_algorithm: str = "HS256"
    auth_service_url: str = "http://auth-service:8001"
    internal_api_key: str = "soa-pickleball-internal-service-key-2026"
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173"
    lock_ttl_seconds: int = 900  # 15 minutes

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip() and o.strip() != "*"]

    def validate_production_settings(self) -> None:
        if self.app_env.lower() != "production":
            return
        for name, val in (
            ("JWT_SECRET", self.jwt_secret),
            ("INTERNAL_API_KEY", self.internal_api_key),
        ):
            if not val or len(val.strip()) < 24 or val.strip() in _INSECURE_DEFAULTS:
                raise RuntimeError(f"Unsafe or missing {name} in production mode")


settings = Settings()
