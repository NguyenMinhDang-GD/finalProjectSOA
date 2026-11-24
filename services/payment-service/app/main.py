from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.events.rabbitmq import rmq_client
from app.metrics import metrics_router, prometheus_middleware
from app.routers.payments import router as payments_router
from app.services.payment_service import start_booking_lifecycle_consumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await rmq_client.connect()
    await start_booking_lifecycle_consumer()

    yield

    await rmq_client.close()
    await engine.dispose()


app = FastAPI(
    title="Pickleball Payment Service",
    version="1.0.0",
    docs_url="/api/payments/docs",
    openapi_url="/api/payments/openapi.json",
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

app.include_router(payments_router)
app.include_router(metrics_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.service_name}
