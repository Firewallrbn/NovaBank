"""Server-Sent Events feed for the real-time UI."""

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

from fastapi import Request


class Broadcaster:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def publish(self, message: dict) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    @contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)


def _format(message: dict) -> str:
    return f"event: {message['type']}\ndata: {json.dumps(message, default=str)}\n\n"


async def sse_events(
    request: Request,
    broadcaster: Broadcaster,
    transfer_id: str | None,
    initial: dict | None,
) -> AsyncIterator[str]:
    with broadcaster.subscribe() as queue:
        yield "retry: 3000\n\n"
        if initial is not None:
            yield _format(initial)
        while not await request.is_disconnected():
            try:
                message = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if transfer_id and message.get("transfer_id") not in (None, transfer_id):
                continue
            yield _format(message)
