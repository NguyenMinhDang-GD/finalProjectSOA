from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "auth-service"
    database_url: str = "postgresql+asyncpg://pickleball:pickleball_secret@localhost:5432/auth_db"
    jwt_secret: str = "soa-pickleball-jwt-super-secret-key-2026"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440


settings = Settings()
