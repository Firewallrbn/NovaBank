"""Idempotency store shared by every domain service: one row per (transfer_id, operation)."""

import sqlite3

from saga_common.contracts import FailureReason, OperationResult, OperationStatus, now_iso
from saga_common.db import row

OPERATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS operations (
    transfer_id TEXT NOT NULL,
    operation   TEXT NOT NULL,
    status      TEXT NOT NULL,
    reason      TEXT,
    detail      TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (transfer_id, operation)
);
"""


def find(conn: sqlite3.Connection, transfer_id: str, operation: str) -> OperationResult | None:
    found = row(
        conn,
        "SELECT transfer_id, operation, status, reason, detail FROM operations WHERE transfer_id = ? AND operation = ?",
        (transfer_id, operation),
    )
    if found is None:
        return None
    return OperationResult(**found, replayed=True)


def record(
    conn: sqlite3.Connection,
    transfer_id: str,
    operation: str,
    status: OperationStatus,
    detail: str,
    reason: FailureReason | None = None,
) -> OperationResult:
    conn.execute(
        "INSERT INTO operations (transfer_id, operation, status, reason, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (transfer_id, operation, status.value, reason.value if reason else None, detail, now_iso()),
    )
    return OperationResult(transfer_id=transfer_id, operation=operation, status=status, reason=reason, detail=detail)
