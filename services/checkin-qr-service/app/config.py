from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "checkin-qr-service"
    database_url: str = "postgresql+asyncpg://pickleball:pickleball_secret@localhost:5432/checkin_db"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_secret: str = "soa-pickleball-jwt-super-secret-key-2026"
    jwt_algorithm: str = "HS256"
    qr_hmac_secret: str = "soa-pickleball-qr-hmac-secret-key-2026"
    allow_demo_bypass_time: bool = True


settings = Settings()
