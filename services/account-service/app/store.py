from saga_common.contracts import now_iso
from saga_common.db import Database
from saga_common.inbox import INBOX_SCHEMA
from saga_common.operations import OPERATIONS_SCHEMA
from saga_common.outbox import OUTBOX_SCHEMA

SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS accounts (
    id            TEXT PRIMARY KEY,
    owner         TEXT NOT NULL,
    balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0),
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_entries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_id         TEXT NOT NULL,
    account_id          TEXT NOT NULL,
    entry_type          TEXT NOT NULL CHECK (entry_type IN ('DEBIT', 'DEBIT_REVERSAL', 'CREDIT')),
    amount_cents        INTEGER NOT NULL,
    balance_after_cents INTEGER NOT NULL,
    created_at          TEXT NOT NULL,
    UNIQUE (transfer_id, entry_type)
);
"""
    + OPERATIONS_SCHEMA
    + OUTBOX_SCHEMA
    + INBOX_SCHEMA
)

SEED_ACCOUNTS = (
    ("ACC-001", "Ana Gómez", 100_000_000),
    ("ACC-002", "Luis Pérez", 50_000_000),
    ("ACC-003", "Marta Ruiz", 5_000_000),
    ("ACC-004", "Carlos Díaz", 25_000_000),
)

_TABLES = ("ledger_entries", "accounts", "operations", "outbox", "processed_events")


def seed(db: Database, reset: bool = False) -> None:
    with db.transaction() as conn:
        if reset:
            for table in _TABLES:
                conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            "INSERT OR IGNORE INTO accounts (id, owner, balance_cents, updated_at) VALUES (?, ?, ?, ?)",
            [(account_id, owner, balance, now_iso()) for account_id, owner, balance in SEED_ACCOUNTS],
        )
