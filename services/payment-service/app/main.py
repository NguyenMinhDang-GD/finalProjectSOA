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
from app.routers.payments import router as payments_router
from app.services.payment_service import start_booking_lifecycle_consumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "postgresql":
            alter_statements = [
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS reconciliation_status VARCHAR(40) NOT NULL DEFAULT 'NONE'",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS reconciliation_note TEXT",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS expected_amount INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS received_amount INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS refunded_amount INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS currency VARCHAR(10) NOT NULL DEFAULT 'VND'",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS payment_mode VARCHAR(20) NOT NULL DEFAULT 'MOCK_DEMO'",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS simulation_notice TEXT NOT NULL DEFAULT 'THANH TOAN GIA LAP'",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS failure_reason TEXT",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS payment_method VARCHAR(30) NOT NULL DEFAULT 'SIMULATED_ONLINE'",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS booking_revision INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS collected_by VARCHAR(150)",
                "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS collected_at TIMESTAMPTZ",
                "ALTER TABLE payment_attempts ADD COLUMN IF NOT EXISTS payment_method VARCHAR(30) NOT NULL DEFAULT 'SIMULATED_ONLINE'",
                "UPDATE payment_transactions SET expected_amount = CAST(ROUND(amount) AS INTEGER) WHERE expected_amount = 0",
                "UPDATE payment_transactions SET received_amount = expected_amount WHERE status = 'SUCCEEDED' AND received_amount = 0",
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_provider_tx_id ON payment_transactions (provider_tx_id) WHERE provider_tx_id IS NOT NULL",
            ]
            for stmt in alter_statements:
                await conn.execute(text(stmt))

    await rmq_client.connect()
    await start_booking_lifecycle_consumer()

    stop_event = asyncio.Event()
    outbox_task = asyncio.create_task(run_outbox_dispatcher(stop_event))

    yield

    stop_event.set()
    await outbox_task
    await rmq_client.close()
    await engine.dispose()


is_prod = settings.app_env.lower() == "production"
app = FastAPI(
    title="Pickleball Payment Service",
    version="1.0.0",
    docs_url=None if is_prod else "/api/payments/docs",
    openapi_url=None if is_prod else "/api/payments/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Guest-Token", "X-Webhook-Signature", "X-Request-Id"],
)
app.middleware("http")(prometheus_middleware)

app.include_router(payments_router)
app.include_router(metrics_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.service_name}
