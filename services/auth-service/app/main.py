from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.metrics import metrics_router, prometheus_middleware
from app.routers.auth import router as auth_router
from app.services.auth_service import seed_default_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_default_users(db)
    yield
    await engine.dispose()


is_prod = settings.app_env.lower() == "production"
app = FastAPI(
    title="Pickleball Auth Service",
    version="1.0.0",
    docs_url=None if is_prod else "/api/auth/docs",
    openapi_url=None if is_prod else "/api/auth/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
)
app.middleware("http")(prometheus_middleware)

app.include_router(auth_router)
app.include_router(metrics_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.service_name}
