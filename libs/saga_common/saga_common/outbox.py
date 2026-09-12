import asyncio
import logging
import sqlite3

from saga_common.contracts import EVENTS_EXCHANGE, DomainEvent, now_iso
from saga_common.db import Database
from saga_common.messaging import MessageBus

log = logging.getLogger(__name__)

OUTBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   TEXT NOT NULL UNIQUE,
    exchange     TEXT NOT NULL,
    routing_key  TEXT NOT NULL,
    body         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    published_at TEXT
);
"""


def enqueue_event(conn: sqlite3.Connection, event: DomainEvent) -> None:
    """Must be called inside the same transaction as the local state change (transactional outbox)."""
    conn.execute(
        "INSERT INTO outbox (message_id, exchange, routing_key, body, created_at) VALUES (?, ?, ?, ?, ?)",
        (event.event_id, EVENTS_EXCHANGE, event.event_type.value, event.model_dump_json(), now_iso()),
    )


class OutboxRelay:
    def __init__(self, db: Database, bus: MessageBus, poll_interval: float = 1.0) -> None:
        self._db = db
        self._bus = bus
        self._poll_interval = poll_interval
        self._wake = asyncio.Event()

    def notify(self) -> None:
        self._wake.set()

    async def run(self) -> None:
        while True:
            self._wake.clear()
            try:
                await self._drain()
            except Exception:
                log.exception("Fallo publicando el outbox; se reintentará")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self._poll_interval)
            except TimeoutError:
                pass

    async def _drain(self) -> None:
        pending = self._db.query(
            "SELECT id, message_id, exchange, routing_key, body FROM outbox "
            "WHERE published_at IS NULL ORDER BY id LIMIT 100"
        )
        for item in pending:
            await self._bus.publish(item["exchange"], item["routing_key"], item["body"].encode(), item["message_id"])
            self._db.execute("UPDATE outbox SET published_at = ? WHERE id = ?", (now_iso(), item["id"]))
