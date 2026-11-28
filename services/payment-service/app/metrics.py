import time
from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
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

PAYMENTS_CONFIRMED_TOTAL = Counter(
    "pickleball_payments_confirmed_total",
    "Total confirmed payments",
    ["provider"],
)

PAYMENTS_FAILED_TOTAL = Counter(
    "pickleball_payments_failed_total",
    "Total failed or underpaid payment attempts",
    ["reason"],
)

PAYMENT_RECONCILIATION_CASES_TOTAL = Counter(
    "pickleball_payment_reconciliation_cases_total",
    "Total reconciliation cases created",
    ["case_type"],
)

REFUNDS_TOTAL = Counter(
    "pickleball_refunds_total",
    "Total refund lifecycle transitions",
    ["status", "policy_tier"],
)

OUTBOX_PENDING_GAUGE = Gauge(
    "pickleball_outbox_pending_events",
    "Current number of pending outbox events",
    ["service"],
)

OUTBOX_PUBLISHED_TOTAL = Counter(
    "pickleball_outbox_published_total",
    "Total outbox events published",
    ["service", "event_type"],
)

OUTBOX_FAILED_TOTAL = Counter(
    "pickleball_outbox_failed_total",
    "Total outbox publication failures",
    ["service", "event_type"],
)

EVENTS_RETRY_TOTAL = Counter(
    "pickleball_consumer_retry_total",
    "Total consumer retries",
    ["service", "event_type"],
)

EVENTS_DUPLICATE_TOTAL = Counter(
    "pickleball_consumer_duplicate_total",
    "Total duplicate events skipped by inbox",
    ["service", "event_type"],
)

EVENTS_DLQ_TOTAL = Counter(
    "pickleball_consumer_dlq_total",
    "Total events routed to DLQ",
    ["service", "event_type"],
)

PAYMENT_COMPENSATION_REQUIRED_TOTAL = Counter(
    "pickleball_payment_compensation_required_total",
    "Total payments flagged as compensation required",
    ["reason"],
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
