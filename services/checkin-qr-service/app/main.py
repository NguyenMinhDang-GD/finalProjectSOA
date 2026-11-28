import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, engine
from app.events.outbox import run_outbox_dispatcher
from app.events.rabbitmq import rmq_client
from app.metrics import metrics_router, prometheus_middleware
from app.routers.checkin import router as checkin_router
from app.services.checkin_service import start_consumers


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "postgresql":
            await conn.execute(text("ALTER TABLE checkin_tickets ADD COLUMN IF NOT EXISTS branch_name VARCHAR(180) NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE checkin_tickets ADD COLUMN IF NOT EXISTS location_name VARCHAR(180) NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE checkin_tickets ADD COLUMN IF NOT EXISTS location_address VARCHAR(300) NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE checkin_tickets ADD COLUMN IF NOT EXISTS booking_revision INTEGER NOT NULL DEFAULT 1"))

    await rmq_client.connect()
    await start_consumers()

    stop_event = asyncio.Event()
    outbox_task = asyncio.create_task(run_outbox_dispatcher(stop_event))

    yield

    stop_event.set()
    await outbox_task
    await rmq_client.close()
    await engine.dispose()


is_prod = settings.app_env.lower() == "production"
app = FastAPI(
    title="Pickleball Check-in & QR Service",
    version="1.1.0",
    docs_url=None if is_prod else "/api/checkin/docs",
    openapi_url=None if is_prod else "/api/checkin/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Guest-Token", "X-Request-Id"],
)
app.middleware("http")(prometheus_middleware)

app.include_router(checkin_router)
app.include_router(metrics_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.service_name}
