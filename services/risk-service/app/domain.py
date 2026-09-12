"""Local transactions of the Risk & Fraud Prevention service."""

import sqlite3

from app.config import DAILY_LIMIT_CENTS, MAX_SINGLE_TRANSFER_CENTS
from saga_common import operations
from saga_common.contracts import (
    FailureReason,
    OperationResult,
    OperationStatus,
    TransferPayload,
    format_money,
    now_iso,
    utcnow,
)
from saga_common.db import Database, row

EVALUATE = "EVALUATE"
REVERT = "REVERT"


def _business_date() -> str:
    return utcnow().date().isoformat()


def _used(conn: sqlite3.Connection, account_id: str, day: str) -> int:
    found = row(conn, "SELECT used_cents FROM daily_usage WHERE account_id = ? AND business_date = ?", (account_id, day))
    return found["used_cents"] if found else 0


def evaluate(conn: sqlite3.Connection, payload: TransferPayload) -> OperationResult:
    transfer_id = payload.transfer_id
    if (previous := operations.find(conn, transfer_id, EVALUATE)) is not None:
        return previous
    if operations.find(conn, transfer_id, REVERT) is not None:
        return operations.record(
            conn, transfer_id, EVALUATE, OperationStatus.REJECTED,
            "Evaluación bloqueada: la aprobación ya fue anulada", FailureReason.CANCELLED,
        )

    account_id = payload.source_account
    amount = payload.amount_cents
    day = _business_date()
    used = _used(conn, account_id, day)

    reason: FailureReason | None = None
    detail = ""
    if payload.chaos.force_fraud:
        reason = FailureReason.FRAUD_SUSPECTED
        detail = "Alerta antifraude: patrón sospechoso detectado (simulación de caos)"
    elif amount > MAX_SINGLE_TRANSFER_CENTS:
        reason = FailureReason.AMOUNT_LIMIT_EXCEEDED
        detail = f"El monto {format_money(amount)} supera el máximo por transacción de {format_money(MAX_SINGLE_TRANSFER_CENTS)}"
    elif used + amount > DAILY_LIMIT_CENTS:
        reason = FailureReason.DAILY_LIMIT_EXCEEDED
        detail = (
            f"Límite diario excedido para {account_id}: usado {format_money(used)} "
            f"de {format_money(DAILY_LIMIT_CENTS)}"
        )

    conn.execute(
        "INSERT INTO risk_evaluations "
        "(transfer_id, account_id, amount_cents, business_date, decision, reason, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (transfer_id, account_id, amount, day, "REJECTED" if reason else "APPROVED",
         reason.value if reason else None, now_iso(), now_iso()),
    )
    if reason is not None:
        return operations.record(conn, transfer_id, EVALUATE, OperationStatus.REJECTED, detail, reason)

    conn.execute(
        "INSERT INTO daily_usage (account_id, business_date, used_cents) VALUES (?, ?, ?) "
        "ON CONFLICT (account_id, business_date) DO UPDATE SET used_cents = used_cents + excluded.used_cents",
        (account_id, day, amount),
    )
    return operations.record(
        conn, transfer_id, EVALUATE, OperationStatus.SUCCEEDED,
        f"Riesgo aprobado: cupo diario de {account_id} usado {format_money(used + amount)} "
        f"de {format_money(DAILY_LIMIT_CENTS)}",
    )


def revert(conn: sqlite3.Connection, transfer_id: str) -> OperationResult:
    if (previous := operations.find(conn, transfer_id, REVERT)) is not None:
        return previous

    evaluation = row(conn, "SELECT * FROM risk_evaluations WHERE transfer_id = ?", (transfer_id,))
    if evaluation is None:
        return operations.record(
            conn, transfer_id, REVERT, OperationStatus.NOOP,
            "Sin evaluación previa; se registra una marca que bloquea una aprobación tardía",
        )
    if evaluation["decision"] != "APPROVED":
        return operations.record(
            conn, transfer_id, REVERT, OperationStatus.NOOP,
            f"No hay aprobación que anular (decisión {evaluation['decision']})",
        )

    conn.execute(
        "UPDATE daily_usage SET used_cents = used_cents - ? WHERE account_id = ? AND business_date = ?",
        (evaluation["amount_cents"], evaluation["account_id"], evaluation["business_date"]),
    )
    conn.execute(
        "UPDATE risk_evaluations SET decision = 'REVERTED', updated_at = ? WHERE transfer_id = ?",
        (now_iso(), transfer_id),
    )
    return operations.record(
        conn, transfer_id, REVERT, OperationStatus.SUCCEEDED,
        f"Aprobación anulada: se liberan {format_money(evaluation['amount_cents'])} "
        f"del cupo diario de {evaluation['account_id']}",
    )


def list_evaluations(db: Database, limit: int) -> list[dict]:
    return db.query("SELECT * FROM risk_evaluations ORDER BY created_at DESC LIMIT ?", (limit,))


def limits(db: Database, account_id: str) -> dict:
    found = db.query_one(
        "SELECT used_cents FROM daily_usage WHERE account_id = ? AND business_date = ?",
        (account_id, _business_date()),
    )
    return {
        "account_id": account_id,
        "business_date": _business_date(),
        "used_cents": found["used_cents"] if found else 0,
        "daily_limit_cents": DAILY_LIMIT_CENTS,
        "max_single_transfer_cents": MAX_SINGLE_TRANSFER_CENTS,
    }
