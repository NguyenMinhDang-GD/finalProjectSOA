from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app.events.rabbitmq import rmq_client
from app.metrics import metrics_router, prometheus_middleware
from app.routers.notifications import router as notifications_router
from app.services.email_service import start_ticket_consumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "postgresql":
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_sent_booking "
                    "ON notification_logs (booking_code) WHERE status = 'SENT'"
                )
            )

    await rmq_client.connect()
    await start_ticket_consumer()

    yield

    await rmq_client.close()
    await engine.dispose()


is_prod = settings.app_env.lower() == "production"
app = FastAPI(
    title="Pickleball Notification Service",
    version="1.0.0",
    docs_url=None if is_prod else "/api/notifications/docs",
    openapi_url=None if is_prod else "/api/notifications/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
)
app.middleware("http")(prometheus_middleware)

app.include_router(notifications_router)
app.include_router(metrics_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.service_name}
