"""Gateway storage: idempotency, transfer read model and the consolidated audit log."""

import json
import sqlite3
from enum import StrEnum
from typing import Any

from app.config import PREFECT_UI_URL
from saga_common.contracts import (
    SAGA_STEPS,
    STEP_STATUS_RANK,
    TERMINAL_STATUSES,
    ChaosConfig,
    SagaMode,
    StepStatus,
    TransferPayload,
    TransferStatus,
    now_iso,
)
from saga_common.db import Database, row
from saga_common.outbox import OUTBOX_SCHEMA

SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS transfers (
    transfer_id         TEXT PRIMARY KEY,
    request_hash        TEXT NOT NULL,
    mode                TEXT NOT NULL,
    source_account      TEXT NOT NULL,
    destination_account TEXT NOT NULL,
    amount_cents        INTEGER NOT NULL,
    chaos               TEXT NOT NULL,
    delay_seconds       REAL NOT NULL,
    status              TEXT NOT NULL,
    failure_reason      TEXT,
    detail              TEXT,
    flow_run_id         TEXT,
    dispatched_at       TEXT,
    duplicate_requests  INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transfer_steps (
    transfer_id TEXT NOT NULL,
    step        TEXT NOT NULL,
    status      TEXT NOT NULL,
    detail      TEXT,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (transfer_id, step)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_id TEXT NOT NULL,
    at          TEXT NOT NULL,
    source      TEXT NOT NULL,
    category    TEXT NOT NULL,
    step        TEXT,
    status      TEXT,
    event_type  TEXT,
    reason      TEXT,
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_transfer ON audit_log (transfer_id, id);
CREATE TABLE IF NOT EXISTS processed_messages (
    message_id   TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
"""
    + OUTBOX_SCHEMA
)

_SKIPPED_DETAIL = "Paso omitido: la saga no llegó a esta fase"


class AuditCategory(StrEnum):
    SOLICITUD = "SOLICITUD"
    DUPLICADO = "DUPLICADO"
    DESPACHO = "DESPACHO"
    PASO = "PASO"
    ESTADO = "ESTADO"
    EVENTO = "EVENTO"


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def add_audit(
    conn: sqlite3.Connection,
    transfer_id: str,
    source: str,
    category: AuditCategory,
    *,
    step: Any = None,
    status: Any = None,
    event_type: Any = None,
    reason: Any = None,
    detail: str | None = None,
    at: str | None = None,
) -> dict:
    entry = {
        "transfer_id": transfer_id,
        "at": at or now_iso(),
        "source": source,
        "category": category.value,
        "step": _text(step),
        "status": _text(status),
        "event_type": _text(event_type),
        "reason": _text(reason),
        "detail": detail,
    }
    cursor = conn.execute(
        "INSERT INTO audit_log (transfer_id, at, source, category, step, status, event_type, reason, detail) "
        "VALUES (:transfer_id, :at, :source, :category, :step, :status, :event_type, :reason, :detail)",
        entry,
    )
    return {"id": cursor.lastrowid, **entry}


def claim_message(conn: sqlite3.Connection, message_id: str) -> bool:
    return conn.execute(
        "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) VALUES (?, ?)", (message_id, now_iso())
    ).rowcount == 1


def insert_transfer(conn: sqlite3.Connection, payload: TransferPayload, mode: SagaMode, request_hash: str) -> None:
    conn.execute(
        "INSERT INTO transfers (transfer_id, request_hash, mode, source_account, destination_account, amount_cents, "
        "chaos, delay_seconds, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            payload.transfer_id, request_hash, mode.value, payload.source_account, payload.destination_account,
            payload.amount_cents, payload.chaos.model_dump_json(), payload.delay_seconds,
            TransferStatus.PENDIENTE.value, now_iso(), now_iso(),
        ),
    )
    conn.executemany(
        "INSERT INTO transfer_steps (transfer_id, step, status, updated_at) VALUES (?, ?, ?, ?)",
        [(payload.transfer_id, step.value, StepStatus.PENDING.value, now_iso()) for step in SAGA_STEPS],
    )


def payload_from_row(transfer: dict) -> TransferPayload:
    return TransferPayload(
        transfer_id=transfer["transfer_id"],
        source_account=transfer["source_account"],
        destination_account=transfer["destination_account"],
        amount_cents=transfer["amount_cents"],
        chaos=ChaosConfig.model_validate_json(transfer["chaos"]),
        delay_seconds=transfer["delay_seconds"],
    )


def apply_step(conn: sqlite3.Connection, transfer_id: str, step: Any, status: Any, detail: str | None) -> bool:
    current = row(conn, "SELECT status FROM transfer_steps WHERE transfer_id = ? AND step = ?", (transfer_id, str(step)))
    if current is None:
        return False
    if STEP_STATUS_RANK[StepStatus(status)] < STEP_STATUS_RANK[StepStatus(current["status"])]:
        return False
    conn.execute(
        "UPDATE transfer_steps SET status = ?, detail = ?, updated_at = ? WHERE transfer_id = ? AND step = ?",
        (str(status), detail, now_iso(), transfer_id, str(step)),
    )
    return True


def apply_status(
    conn: sqlite3.Connection,
    transfer_id: str,
    status: TransferStatus,
    reason: Any = None,
    detail: str | None = None,
    flow_run_id: str | None = None,
) -> bool:
    current = row(conn, "SELECT status FROM transfers WHERE transfer_id = ?", (transfer_id,))
    if current is None:
        return False
    if flow_run_id:
        conn.execute(
            "UPDATE transfers SET flow_run_id = COALESCE(flow_run_id, ?) WHERE transfer_id = ?", (flow_run_id, transfer_id)
        )
    current_status = TransferStatus(current["status"])
    if current_status in TERMINAL_STATUSES:
        return False
    if status is TransferStatus.EN_PROCESO and current_status is TransferStatus.COMPENSANDO:
        return False

    conn.execute(
        "UPDATE transfers SET status = ?, failure_reason = COALESCE(?, failure_reason), detail = COALESCE(?, detail), "
        "updated_at = ? WHERE transfer_id = ?",
        (status.value, _text(reason), detail, now_iso(), transfer_id),
    )
    if status in TERMINAL_STATUSES:
        conn.execute(
            "UPDATE transfer_steps SET status = ?, detail = ?, updated_at = ? WHERE transfer_id = ? AND status = ?",
            (StepStatus.SKIPPED.value, _SKIPPED_DETAIL, now_iso(), transfer_id, StepStatus.PENDING.value),
        )
    return True


def _serialize(transfer: dict, steps: list[dict]) -> dict:
    order = {step.value: index for index, step in enumerate(SAGA_STEPS)}
    flow_run_id = transfer["flow_run_id"]
    return {
        "transfer_id": transfer["transfer_id"],
        "mode": transfer["mode"],
        "source_account": transfer["source_account"],
        "destination_account": transfer["destination_account"],
        "amount_cents": transfer["amount_cents"],
        "chaos": json.loads(transfer["chaos"]),
        "delay_seconds": transfer["delay_seconds"],
        "status": transfer["status"],
        "failure_reason": transfer["failure_reason"],
        "detail": transfer["detail"],
        "duplicate_requests": transfer["duplicate_requests"],
        "created_at": transfer["created_at"],
        "updated_at": transfer["updated_at"],
        "steps": sorted(
            ({k: s[k] for k in ("step", "status", "detail", "updated_at")} for s in steps),
            key=lambda s: order[s["step"]],
        ),
        "prefect": {
            "flow_run_id": flow_run_id,
            "flow_run_url": f"{PREFECT_UI_URL}/runs/flow-run/{flow_run_id}" if flow_run_id else None,
            "tag": f"transfer:{transfer['transfer_id']}",
        },
    }


def snapshot(db: Database, transfer_id: str) -> dict | None:
    transfer = db.query_one("SELECT * FROM transfers WHERE transfer_id = ?", (transfer_id,))
    if transfer is None:
        return None
    steps = db.query("SELECT * FROM transfer_steps WHERE transfer_id = ?", (transfer_id,))
    return _serialize(transfer, steps)


def list_transfers(db: Database, limit: int) -> list[dict]:
    transfers = db.query("SELECT * FROM transfers ORDER BY created_at DESC LIMIT ?", (limit,))
    if not transfers:
        return []
    ids = [t["transfer_id"] for t in transfers]
    placeholders = ", ".join("?" for _ in ids)
    steps_by_transfer: dict[str, list[dict]] = {}
    for step in db.query(f"SELECT * FROM transfer_steps WHERE transfer_id IN ({placeholders})", tuple(ids)):
        steps_by_transfer.setdefault(step["transfer_id"], []).append(step)
    return [_serialize(t, steps_by_transfer.get(t["transfer_id"], [])) for t in transfers]


def audit_for(db: Database, transfer_id: str) -> list[dict]:
    return db.query("SELECT * FROM audit_log WHERE transfer_id = ? ORDER BY id", (transfer_id,))


def recent_audit(db: Database, limit: int) -> list[dict]:
    return db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


def in_flight_count(db: Database) -> int:
    placeholders = ", ".join("?" for _ in TERMINAL_STATUSES)
    found = db.query_one(
        f"SELECT COUNT(*) AS n FROM transfers WHERE status NOT IN ({placeholders})",
        tuple(s.value for s in TERMINAL_STATUSES),
    )
    return found["n"] if found else 0


def reset(db: Database) -> None:
    with db.transaction() as conn:
        for table in ("transfer_steps", "transfers", "audit_log", "processed_messages", "outbox"):
            conn.execute(f"DELETE FROM {table}")
