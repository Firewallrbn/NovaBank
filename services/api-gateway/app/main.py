import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DB_PATH, PROJECTION_QUEUE, RABBITMQ_URL, SERVICE_NAME, TELEMETRY_QUEUE
from app.dispatcher import Dispatcher
from app.projection import Projection
from app.routes import router
from app.store import SCHEMA
from app.stream import Broadcaster
from app.tracer import SagaTracer
from saga_common.db import Database
from saga_common.logs import configure_logging
from saga_common.messaging import MessageBus
from saga_common.outbox import OutboxRelay

configure_logging(SERVICE_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db = Database(DB_PATH, SCHEMA)
    bus = MessageBus(RABBITMQ_URL)
    await bus.connect()
    http = httpx.AsyncClient(timeout=10)

    broadcaster = Broadcaster()
    tracer = SagaTracer()
    projection = Projection(db, broadcaster, tracer)
    relay = OutboxRelay(db, bus)
    dispatcher = Dispatcher(db, http, projection)

    app.state.db = db
    app.state.http = http
    app.state.broadcaster = broadcaster
    app.state.projection = projection
    app.state.relay = relay
    app.state.dispatcher = dispatcher

    background = [asyncio.create_task(relay.run()), asyncio.create_task(dispatcher.retry_loop())]
    await bus.subscribe(TELEMETRY_QUEUE, projection.on_telemetry)
    await bus.subscribe(PROJECTION_QUEUE, projection.on_event)
    try:
        yield
    finally:
        for task in background:
            task.cancel()
        tracer.cancel_all()
        await http.aclose()
        await bus.close()


app = FastAPI(title="NovaBank · API Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Idempotency-Key", "Idempotency-Replayed"],
)
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME}
