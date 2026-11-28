import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection
from app.config import settings

logger = logging.getLogger(__name__)
EXCHANGE_NAME = "pickleball.events"
DLX_NAME = "pickleball.dlx"
DLQ_NAME = "pickleball.dlq"


class RabbitMQClient:
    def __init__(self) -> None:
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractRobustChannel | None = None
        self.exchange: aio_pika.abc.AbstractExchange | None = None
        self._consumer_setup: Callable[[], Awaitable[None]] | None = None

    def set_consumer_setup(self, fn: Callable[[], Awaitable[None]]) -> None:
        self._consumer_setup = fn

    async def _init_channel_and_topology(self) -> None:
        assert self.connection is not None
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=5)

        self.exchange = await self.channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        dlx = await self.channel.declare_exchange(
            DLX_NAME, aio_pika.ExchangeType.FANOUT, durable=True
        )
        dlq = await self.channel.declare_queue(DLQ_NAME, durable=True)
        await dlq.bind(dlx)

    async def _on_reconnect(self, _conn: Any) -> None:
        try:
            logger.info("RabbitMQ reconnected; re-initializing channel, topology, and consumers")
            await self._init_channel_and_topology()
            if self._consumer_setup:
                await self._consumer_setup()
        except Exception as exc:
            logger.exception("Error re-initializing RabbitMQ after reconnect: %s", exc)

    async def connect(self) -> None:
        for attempt in range(1, 16):
            try:
                self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
                break
            except Exception as exc:
                if attempt == 15:
                    raise
                logger.warning("RabbitMQ not ready (attempt %s/15): %s", attempt, exc)
                await asyncio.sleep(2)
        assert self.connection is not None
        self.connection.reconnect_callbacks.add(self._on_reconnect)
        await self._init_channel_and_topology()

    async def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()


rmq_client = RabbitMQClient()
