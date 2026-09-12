"""Local transactions of the Account & Ledger service, shared by the HTTP API and the event handlers."""

import sqlite3

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

DEBIT = "DEBIT"
DEBIT_REVERSAL = "DEBIT_REVERSAL"
CREDIT = "CREDIT"


def _balance(conn: sqlite3.Connection, account_id: str) -> int | None:
    found = row(conn, "SELECT balance_cents FROM accounts WHERE id = ?", (account_id,))
    return found["balance_cents"] if found else None


def _ledger(conn: sqlite3.Connection, transfer_id: str, account_id: str, entry_type: str, amount_cents: int) -> int:
    balance = _balance(conn, account_id)
    conn.execute(
        "INSERT INTO ledger_entries "
        "(transfer_id, account_id, entry_type, amount_cents, balance_after_cents, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (transfer_id, account_id, entry_type, amount_cents, balance, now_iso()),
    )
    return balance


def debit(conn: sqlite3.Connection, payload: TransferPayload) -> OperationResult:
    transfer_id = payload.transfer_id
    if (previous := operations.find(conn, transfer_id, DEBIT)) is not None:
        return previous
    if operations.find(conn, transfer_id, DEBIT_REVERSAL) is not None:
        return operations.record(
            conn, transfer_id, DEBIT, OperationStatus.REJECTED,
            "Débito bloqueado: la transferencia ya fue compensada", FailureReason.CANCELLED,
        )

    missing = [a for a in (payload.source_account, payload.destination_account) if _balance(conn, a) is None]
    if missing:
        return operations.record(
            conn, transfer_id, DEBIT, OperationStatus.REJECTED,
            f"Cuenta inexistente: {', '.join(missing)}", FailureReason.ACCOUNT_NOT_FOUND,
        )

    amount = payload.amount_cents
    source = payload.source_account
    # Check-and-debit in a single atomic statement: the balance can never go negative.
    updated = conn.execute(
        "UPDATE accounts SET balance_cents = balance_cents - ?, updated_at = ? WHERE id = ? AND balance_cents >= ?",
        (amount, now_iso(), source, amount),
    ).rowcount
    if updated == 0:
        available = _balance(conn, source)
        return operations.record(
            conn, transfer_id, DEBIT, OperationStatus.REJECTED,
            f"Fondos insuficientes en {source}: disponible {format_money(available)}, requerido {format_money(amount)}",
            FailureReason.INSUFFICIENT_FUNDS,
        )

    balance = _ledger(conn, transfer_id, source, DEBIT, -amount)
    return operations.record(
        conn, transfer_id, DEBIT, OperationStatus.SUCCEEDED,
        f"Débito de {format_money(amount)} en {source} (nuevo saldo {format_money(balance)})",
    )


def refund_debit(conn: sqlite3.Connection, transfer_id: str) -> OperationResult:
    if (previous := operations.find(conn, transfer_id, DEBIT_REVERSAL)) is not None:
        return previous

    entry = row(
        conn,
        "SELECT account_id, amount_cents FROM ledger_entries WHERE transfer_id = ? AND entry_type = 'DEBIT'",
        (transfer_id,),
    )
    if entry is None:
        return operations.record(
            conn, transfer_id, DEBIT_REVERSAL, OperationStatus.NOOP,
            "Sin débito previo que reintegrar; se registra una marca que bloquea un débito tardío",
        )

    amount = -entry["amount_cents"]
    account_id = entry["account_id"]
    conn.execute(
        "UPDATE accounts SET balance_cents = balance_cents + ?, updated_at = ? WHERE id = ?",
        (amount, now_iso(), account_id),
    )
    balance = _ledger(conn, transfer_id, account_id, DEBIT_REVERSAL, amount)
    return operations.record(
        conn, transfer_id, DEBIT_REVERSAL, OperationStatus.SUCCEEDED,
        f"Reintegro de {format_money(amount)} en {account_id} (saldo restituido {format_money(balance)})",
    )


def credit(conn: sqlite3.Connection, payload: TransferPayload) -> OperationResult:
    transfer_id = payload.transfer_id
    if (previous := operations.find(conn, transfer_id, CREDIT)) is not None:
        return previous

    destination = payload.destination_account
    if _balance(conn, destination) is None:
        return operations.record(
            conn, transfer_id, CREDIT, OperationStatus.REJECTED,
            f"Cuenta destino inexistente: {destination}", FailureReason.ACCOUNT_NOT_FOUND,
        )

    amount = payload.amount_cents
    conn.execute(
        "UPDATE accounts SET balance_cents = balance_cents + ?, updated_at = ? WHERE id = ?",
        (amount, now_iso(), destination),
    )
    balance = _ledger(conn, transfer_id, destination, CREDIT, amount)
    return operations.record(
        conn, transfer_id, CREDIT, OperationStatus.SUCCEEDED,
        f"Crédito de {format_money(amount)} en {destination} (nuevo saldo {format_money(balance)})",
    )


def list_accounts(db: Database) -> list[dict]:
    return db.query("SELECT id, owner, balance_cents, updated_at FROM accounts ORDER BY id")


def ledger(db: Database, account_id: str | None, transfer_id: str | None, limit: int) -> list[dict]:
    clauses, params = [], []
    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    if transfer_id:
        clauses.append("transfer_id = ?")
        params.append(transfer_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return db.query(f"SELECT * FROM ledger_entries {where} ORDER BY id DESC LIMIT ?", (*params, limit))
