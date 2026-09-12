import asyncio
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractIncomingMessage, AbstractRobustConnection

from saga_common.contracts import EVENTS_EXCHANGE, QUEUE_BINDINGS, TELEMETRY_EXCHANGE

log = logging.getLogger(__name__)

Handler = Callable[[bytes], Awaitable[None]]


class MessageBus:
    def __init__(self, url: str) -> None:
        self._url = url
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchanges: dict[str, AbstractExchange] = {}

    async def connect(self, attempts: int = 60, delay: float = 2.0) -> None:
        for attempt in range(1, attempts + 1):
            try:
                self._connection = await aio_pika.connect_robust(self._url)
                break
            except Exception as exc:
                log.warning("RabbitMQ no disponible (intento %s/%s): %s", attempt, attempts, exc)
                await asyncio.sleep(delay)
        else:
            raise RuntimeError("No se pudo conectar a RabbitMQ")

        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)
        for name in (EVENTS_EXCHANGE, TELEMETRY_EXCHANGE):
            self._exchanges[name] = await self._channel.declare_exchange(
                name, aio_pika.ExchangeType.TOPIC, durable=True
            )
        for queue_name, (exchange, routing_keys) in QUEUE_BINDINGS.items():
            queue = await self._channel.declare_queue(queue_name, durable=True)
            for key in routing_keys:
                await queue.bind(self._exchanges[exchange], routing_key=str(key))

    async def publish(self, exchange: str, routing_key: str, body: bytes, message_id: str) -> None:
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            message_id=message_id,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchanges[exchange].publish(message, routing_key=routing_key)

    async def subscribe(self, queue_name: str, handler: Handler) -> None:
        """At-least-once consumption: ack only after the handler succeeds, requeue otherwise."""
        assert self._channel is not None
        queue = await self._channel.get_queue(queue_name)

        async def on_message(message: AbstractIncomingMessage) -> None:
            try:
                await handler(message.body)
            except Exception:
                log.exception("Error procesando mensaje %s en %s; se reencola", message.message_id, queue_name)
                await asyncio.sleep(2)
                await message.nack(requeue=True)
            else:
                await message.ack()

        await queue.consume(on_message)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
