from saga_common.db import Database
from saga_common.inbox import INBOX_SCHEMA
from saga_common.operations import OPERATIONS_SCHEMA
from saga_common.outbox import OUTBOX_SCHEMA

SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS risk_evaluations (
    transfer_id   TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    amount_cents  INTEGER NOT NULL,
    business_date TEXT NOT NULL,
    decision      TEXT NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED', 'REVERTED')),
    reason        TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_usage (
    account_id    TEXT NOT NULL,
    business_date TEXT NOT NULL,
    used_cents    INTEGER NOT NULL CHECK (used_cents >= 0),
    PRIMARY KEY (account_id, business_date)
);
"""
    + OPERATIONS_SCHEMA
    + OUTBOX_SCHEMA
    + INBOX_SCHEMA
)

_TABLES = ("risk_evaluations", "daily_usage", "operations", "outbox", "processed_events")


def reset(db: Database) -> None:
    with db.transaction() as conn:
        for table in _TABLES:
            conn.execute(f"DELETE FROM {table}")
