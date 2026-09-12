"""Local transactions of the Interbank Clearing Gateway.

Settling is split in two because the external network call is asynchronous and cannot live
inside a SQLite transaction: `contact_network` records the network outcome on a PENDING row,
and `finalize` turns that outcome into the final (idempotent) result.
"""

import asyncio
import sqlite3
from uuid import uuid4

from app.config import NETWORK_TIMEOUT_SECONDS
from saga_common import operations
from saga_common.contracts import (
    FailureReason,
    OperationResult,
    OperationStatus,
    TransferPayload,
    format_money,
    now_iso,
)
from saga_common.db import Database, row

SETTLE = "SETTLE"
CANCEL = "CANCEL"


async def _external_network(payload: TransferPayload) -> str:
    if payload.chaos.clearing_timeout:
        await asyncio.sleep(3600)  # simulated outage: the external network never answers
    await asyncio.sleep(0.2)
    return f"CLR-{uuid4().hex[:10].upper()}"


async def contact_network(db: Database, payload: TransferPayload) -> None:
    transfer_id = payload.transfer_id
    with db.transaction() as conn:
        if operations.find(conn, transfer_id, SETTLE) or operations.find(conn, transfer_id, CANCEL):
            return
        current = row(conn, "SELECT network_outcome FROM settlements WHERE transfer_id = ?", (transfer_id,))
        if current is not None and current["network_outcome"] is not None:
            return
        if current is None:
            conn.execute(
                "INSERT INTO settlements "
                "(transfer_id, source_account, destination_account, amount_cents, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'PENDING', ?, ?)",
                (transfer_id, payload.source_account, payload.destination_account,
                 payload.amount_cents, now_iso(), now_iso()),
            )

    try:
        reference = await asyncio.wait_for(_external_network(payload), timeout=NETWORK_TIMEOUT_SECONDS)
        outcome = "OK"
    except TimeoutError:
        reference, outcome = None, "TIMEOUT"

    db.execute(
        "UPDATE settlements SET network_outcome = ?, external_reference = ?, updated_at = ? "
        "WHERE transfer_id = ? AND status = 'PENDING' AND network_outcome IS NULL",
        (outcome, reference, now_iso(), transfer_id),
    )


def finalize(conn: sqlite3.Connection, payload: TransferPayload) -> OperationResult:
    transfer_id = payload.transfer_id
    if (previous := operations.find(conn, transfer_id, SETTLE)) is not None:
        return previous

    current = row(conn, "SELECT * FROM settlements WHERE transfer_id = ?", (transfer_id,))
    if current is None or current["status"] == "CANCELLED":
        return operations.record(
            conn, transfer_id, SETTLE, OperationStatus.REJECTED,
            "Liquidación anulada antes de completarse", FailureReason.CANCELLED,
        )
    if current["network_outcome"] == "OK":
        conn.execute(
            "UPDATE settlements SET status = 'SETTLED', updated_at = ? WHERE transfer_id = ?",
            (now_iso(), transfer_id),
        )
        return operations.record(
            conn, transfer_id, SETTLE, OperationStatus.SUCCEEDED,
            f"Liquidación de {format_money(payload.amount_cents)} confirmada por la red interbancaria "
            f"(ref. {current['external_reference']})",
        )
    if current["network_outcome"] == "TIMEOUT":
        conn.execute(
            "UPDATE settlements SET status = 'FAILED', reason = ?, updated_at = ? WHERE transfer_id = ?",
            (FailureReason.NETWORK_TIMEOUT.value, now_iso(), transfer_id),
        )
        return operations.record(
            conn, transfer_id, SETTLE, OperationStatus.REJECTED,
            f"La red interbancaria no respondió en {NETWORK_TIMEOUT_SECONDS:g} s: liquidación no realizada",
            FailureReason.NETWORK_TIMEOUT,
        )
    raise RuntimeError("La red interbancaria aún no ha respondido")


def cancel(conn: sqlite3.Connection, transfer_id: str) -> OperationResult:
    if (previous := operations.find(conn, transfer_id, CANCEL)) is not None:
        return previous

    current = row(conn, "SELECT status FROM settlements WHERE transfer_id = ?", (transfer_id,))
    if current is None:
        conn.execute(
            "INSERT INTO settlements (transfer_id, status, created_at, updated_at) VALUES (?, 'CANCELLED', ?, ?)",
            (transfer_id, now_iso(), now_iso()),
        )
        return operations.record(
            conn, transfer_id, CANCEL, OperationStatus.NOOP,
            "Sin liquidación previa; se registra una marca que bloquea una liquidación tardía",
        )

    status = current["status"]
    if status == "PENDING":
        new_status, detail = "CANCELLED", "Liquidación pendiente anulada antes de enviarse a la red"
    elif status == "SETTLED":
        new_status, detail = "REVERSED", "Liquidación revertida en la red interbancaria"
    else:
        return operations.record(
            conn, transfer_id, CANCEL, OperationStatus.NOOP, f"Nada que anular: la liquidación está en estado {status}"
        )
    conn.execute(
        "UPDATE settlements SET status = ?, updated_at = ? WHERE transfer_id = ?", (new_status, now_iso(), transfer_id)
    )
    return operations.record(conn, transfer_id, CANCEL, OperationStatus.SUCCEEDED, detail)


def list_settlements(db: Database, limit: int) -> list[dict]:
    return db.query("SELECT * FROM settlements ORDER BY created_at DESC LIMIT ?", (limit,))
