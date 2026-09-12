import sqlite3

from saga_common.contracts import now_iso
from saga_common.db import Database

INBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_events (
    event_id     TEXT NOT NULL,
    consumer     TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (event_id, consumer)
);
"""


def is_processed(db: Database, event_id: str, consumer: str) -> bool:
    return db.query_one(
        "SELECT 1 FROM processed_events WHERE event_id = ? AND consumer = ?", (event_id, consumer)
    ) is not None


def claim(conn: sqlite3.Connection, event_id: str, consumer: str) -> bool:
    """Registers the event inside the handler's transaction. False means it was already processed."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO processed_events (event_id, consumer, processed_at) VALUES (?, ?, ?)",
        (event_id, consumer, now_iso()),
    )
    return cursor.rowcount == 1
