import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import deployments, flows
from app.api import router
from app.clients import BankingClients
from app.config import (
    DB_PATH,
    DEPLOYMENT_POLL_SECONDS,
    HTTP_TIMEOUT_SECONDS,
    RABBITMQ_URL,
    RECOVERY_INTERVAL_SECONDS,
    SERVICE_NAME,
)
from app.runner import SagaRunner
from app.tracker import SCHEMA, SagaTracker
from saga_common.db import Database
from saga_common.logs import configure_logging
from saga_common.messaging import MessageBus
from saga_common.telemetry import Telemetry

configure_logging(SERVICE_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db = Database(DB_PATH, SCHEMA)
    bus = MessageBus(RABBITMQ_URL)
    await bus.connect()
    http = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)

    tracker = SagaTracker(db, Telemetry(bus, SERVICE_NAME))
    flows.runtime.tracker = tracker
    flows.runtime.clients = BankingClients(http)
    runner = SagaRunner(tracker)
    app.state.tracker = tracker
    app.state.runner = runner

    background = [asyncio.create_task(runner.recovery_loop(RECOVERY_INTERVAL_SECONDS))]
    if (serving := await deployments.register(DEPLOYMENT_POLL_SECONDS)) is not None:
        background.append(serving)
    try:
        yield
    finally:
        for task in background:
            task.cancel()
        await http.aclose()
        await bus.close()


app = FastAPI(title="NovaBank · Orquestador de Sagas", lifespan=lifespan)
app.include_router(router)
