from pydantic_settings import BaseSettings

_INSECURE_DEFAULTS = {
    "",
    "soa-pickleball-jwt-super-secret-key-2026",
    "change-in-production",
}


class Settings(BaseSettings):
    service_name: str = "notification-service"
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://pickleball:pickleball_secret@localhost:5432/notification_db"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_secret: str = "soa-pickleball-jwt-super-secret-key-2026"
    jwt_algorithm: str = "HS256"
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_from: str = "noreply@pickleball-soa.vn"
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip() and o.strip() != "*"]

    def validate_production_settings(self) -> None:
        if self.app_env.lower() != "production":
            return
        if not self.jwt_secret or len(self.jwt_secret.strip()) < 24 or self.jwt_secret.strip() in _INSECURE_DEFAULTS:
            raise RuntimeError("Unsafe or missing JWT_SECRET in production mode")


settings = Settings()
