from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "court-booking-service"
    database_url: str = "postgresql+asyncpg://pickleball:pickleball_secret@localhost:5432/booking_db"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_secret: str = "soa-pickleball-jwt-super-secret-key-2026"
    jwt_algorithm: str = "HS256"
    internal_api_key: str = "soa-pickleball-internal-service-key-2026"
    lock_ttl_seconds: int = 900  # 15 minutes


settings = Settings()
