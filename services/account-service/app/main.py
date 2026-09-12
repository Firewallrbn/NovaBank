from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import store
from app.api import router
from app.config import DB_PATH, QUEUE_NAME, RABBITMQ_URL, SERVICE_NAME
from app.handlers import build_reactions
from saga_common.choreography import run_participant
from saga_common.db import Database
from saga_common.logs import configure_logging

configure_logging(SERVICE_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db = Database(DB_PATH, store.SCHEMA)
    store.seed(db)
    app.state.db = db
    async with run_participant(SERVICE_NAME, QUEUE_NAME, db, RABBITMQ_URL, build_reactions(db)):
        yield


app = FastAPI(title="NovaBank · Account & Ledger", lifespan=lifespan)
app.include_router(router)
