import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.events.rabbitmq import rmq_client
from app.metrics import (
    OUTBOX_FAILED_TOTAL,
    OUTBOX_PENDING_GAUGE,
    OUTBOX_PUBLISHED_TOTAL,
)
from app.models import InboxEvent, OutboxEvent

logger = logging.getLogger(__name__)
MAX_OUTBOX_RETRIES = 10


def enqueue_outbox_event(
    db: AsyncSession,
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    causation_id: str | None = None,
    schema_version: int = 1,
) -> OutboxEvent:
    event_id = uuid.uuid4()
    corr = correlation_id or str(event_id)
    enriched_payload = {
        **payload,
        "event": event_type,
        "event_id": str(event_id),
        "schema_version": schema_version,
        "correlation_id": corr,
    }
    if causation_id:
        enriched_payload["causation_id"] = causation_id

    record = OutboxEvent(
        id=event_id,
        event_type=event_type,
        aggregate_id=str(aggregate_id),
        schema_version=schema_version,
        correlation_id=corr,
        causation_id=causation_id,
        payload=enriched_payload,
        status="PENDING",
    )
    db.add(record)
    return record


def resolve_event_id(data: dict[str, Any], fallback_key: str) -> str:
    if data.get("event_id"):
        return str(data["event_id"])
    digest = hashlib.sha256(fallback_key.encode("utf-8")).hexdigest()[:32]
    return f"legacy:{digest}"


async def claim_inbox_event(
    db: AsyncSession,
    consumer_name: str,
    event_id: str,
    event_type: str,
    correlation_id: str | None = None,
) -> bool:
    stmt = (
        pg_insert(InboxEvent)
        .values(
            id=uuid.uuid4(),
            consumer_name=consumer_name,
            event_id=event_id,
            event_type=event_type,
            correlation_id=correlation_id,
            status="PROCESSED",
            processed_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=["consumer_name", "event_id"])
        .returning(InboxEvent.id)
    )
    inserted = await db.scalar(stmt)
    return inserted is not None


async def dispatch_pending_outbox_once() -> int:
    dispatched = 0
    now_utc = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        pending_count = (
            await db.scalar(
                select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "PENDING")
            )
            or 0
        )
        OUTBOX_PENDING_GAUGE.labels(service=settings.service_name).set(pending_count)

        rows = (
            await db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.status == "PENDING", OutboxEvent.next_retry_at <= now_utc)
                .order_by(OutboxEvent.created_at)
                .limit(20)
                .with_for_update(skip_locked=True)
            )
        ).all()

        for row in rows:
            try:
                await rmq_client.publish(
                    routing_key=row.event_type,
                    payload=row.payload,
                    message_id=str(row.id),
                    correlation_id=row.correlation_id,
                )
                row.status = "PUBLISHED"
                row.published_at = datetime.now(timezone.utc)
                row.last_error = None
                OUTBOX_PUBLISHED_TOTAL.labels(
                    service=settings.service_name, event_type=row.event_type
                ).inc()
                dispatched += 1
            except Exception as exc:
                row.retry_count += 1
                row.last_error = str(exc)[:500]
                OUTBOX_FAILED_TOTAL.labels(
                    service=settings.service_name, event_type=row.event_type
                ).inc()
                if row.retry_count >= MAX_OUTBOX_RETRIES:
                    row.status = "FAILED"
                    logger.error(
                        "Outbox event permanently failed event_id=%s type=%s err=%s",
                        row.id,
                        row.event_type,
                        row.last_error,
                    )
                else:
                    delay_sec = min(60, 2 ** min(row.retry_count, 6))
                    row.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_sec)
                    logger.warning(
                        "Outbox publish retry %s/%s event_id=%s type=%s next_in=%ss err=%s",
                        row.retry_count,
                        MAX_OUTBOX_RETRIES,
                        row.id,
                        row.event_type,
                        delay_sec,
                        row.last_error,
                    )

        await db.commit()
    return dispatched


async def run_outbox_dispatcher(stop_event: asyncio.Event, poll_interval: float = 1.0) -> None:
    while not stop_event.is_set():
        try:
            await dispatch_pending_outbox_once()
        except Exception as exc:
            logger.exception("Outbox dispatcher loop error: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
        except TimeoutError:
            continue


async def list_failed_outbox_events() -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.status == "FAILED")
                .order_by(OutboxEvent.created_at)
            )
        ).all()
        return [
            {
                "event_id": str(r.id),
                "event_type": r.event_type,
                "aggregate_id": r.aggregate_id,
                "retry_count": r.retry_count,
                "last_error": r.last_error,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


async def requeue_failed_outbox_event(event_id: str | None = None) -> int:
    now_utc = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        stmt = select(OutboxEvent).where(OutboxEvent.status == "FAILED")
        if event_id:
            stmt = stmt.where(OutboxEvent.id == uuid.UUID(event_id))
        rows = (await db.scalars(stmt.with_for_update())).all()
        for r in rows:
            r.status = "PENDING"
            r.retry_count = 0
            r.next_retry_at = now_utc
            r.last_error = None
        await db.commit()
        return len(rows)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Outbox operator recovery CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-failed")
    retry_p = sub.add_parser("retry-failed")
    retry_p.add_argument("--event-id", default=None)
    args = parser.parse_args()

    if args.cmd == "list-failed":
        print(json.dumps(asyncio.run(list_failed_outbox_events()), indent=2))
    elif args.cmd == "retry-failed":
        count = asyncio.run(requeue_failed_outbox_event(args.event_id))
        print(json.dumps({"requeued": count}))
