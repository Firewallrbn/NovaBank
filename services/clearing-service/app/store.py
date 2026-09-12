from saga_common.db import Database
from saga_common.inbox import INBOX_SCHEMA
from saga_common.operations import OPERATIONS_SCHEMA
from saga_common.outbox import OUTBOX_SCHEMA

SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS settlements (
    transfer_id         TEXT PRIMARY KEY,
    source_account      TEXT,
    destination_account TEXT,
    amount_cents        INTEGER,
    status              TEXT NOT NULL CHECK (status IN ('PENDING', 'SETTLED', 'FAILED', 'CANCELLED', 'REVERSED')),
    network_outcome     TEXT,
    external_reference  TEXT,
    reason              TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
"""
    + OPERATIONS_SCHEMA
    + OUTBOX_SCHEMA
    + INBOX_SCHEMA
)

_TABLES = ("settlements", "operations", "outbox", "processed_events")


def reset(db: Database) -> None:
    with db.transaction() as conn:
        for table in _TABLES:
            conn.execute(f"DELETE FROM {table}")
