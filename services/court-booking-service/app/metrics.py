import time
from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from app.config import settings

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "route", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "route"],
)

BOOKINGS_CREATED_TOTAL = Counter(
    "pickleball_bookings_created_total",
    "Total bookings created",
    ["court_type", "customer_type"],
)

BOOKINGS_EXPIRED_TOTAL = Counter(
    "pickleball_bookings_expired_total",
    "Total bookings automatically expired",
)

BOOKINGS_PAID_TOTAL = Counter(
    "pickleball_bookings_paid_total",
    "Total bookings confirmed paid via RabbitMQ",
)

metrics_router = APIRouter(tags=["Observability"])


@metrics_router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def prometheus_middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)
    start = time.perf_counter()
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        elapsed = time.perf_counter() - start
        route_obj = request.scope.get("route")
        route_path = getattr(route_obj, "path", request.url.path)
        HTTP_REQUESTS_TOTAL.labels(
            service=settings.service_name,
            method=request.method,
            route=route_path,
            status_code=status_code,
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            service=settings.service_name,
            method=request.method,
            route=route_path,
        ).observe(elapsed)
