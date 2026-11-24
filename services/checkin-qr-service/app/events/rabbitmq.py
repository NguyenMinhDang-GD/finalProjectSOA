import json
import logging
from typing import Any
import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection
from app.config import settings

logger = logging.getLogger(__name__)
EXCHANGE_NAME = "pickleball.events"


class RabbitMQClient:
    def __init__(self) -> None:
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractRobustChannel | None = None
        self.exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)
        self.exchange = await self.channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        if not self.exchange:
            return
        body = json.dumps(payload, default=str).encode("utf-8")
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.exchange.publish(message, routing_key=routing_key)
        logger.info("Published event %s for %s", routing_key, payload.get("booking_code"))

    async def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()


rmq_client = RabbitMQClient()
