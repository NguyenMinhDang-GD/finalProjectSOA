import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.events.rabbitmq import rmq_client
from app.metrics import metrics_router, prometheus_middleware
from app.routers.bookings import router as bookings_router
from app.routers.courts import router as courts_router
from app.services.booking_service import (
    run_expiration_worker,
    seed_courts_and_pricing,
    start_payment_consumer,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_court_slot "
                "ON booking_slots (court_id, play_date, start_hour) "
                "WHERE slot_status IN ('LOCKED', 'BOOKED')"
            )
        )

    async with AsyncSessionLocal() as db:
        await seed_courts_and_pricing(db)

    redis_client = redis_from_url(settings.redis_url, decode_responses=True)
    app.state.redis = redis_client

    await rmq_client.connect()
    await start_payment_consumer(redis_client)

    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(run_expiration_worker(redis_client, stop_event))

    yield

    stop_event.set()
    await worker_task
    await rmq_client.close()
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title="Pickleball Court & Booking Service",
    version="1.0.0",
    docs_url="/api/bookings/docs",
    openapi_url="/api/bookings/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(prometheus_middleware)

app.include_router(courts_router)
app.include_router(bookings_router)
app.include_router(metrics_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.service_name}
