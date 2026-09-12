"""Passive read model: it listens to telemetry and domain events and never commands any service."""

from collections.abc import Callable

from app.config import SERVICE_NAME
from app.store import AuditCategory, add_audit, apply_status, apply_step, claim_message, snapshot
from app.stream import Broadcaster
from saga_common.contracts import (
    DomainEvent,
    EventType,
    TelemetryKind,
    TelemetryMessage,
    TransferStatus,
    status_for_failure,
)
from saga_common.db import Database

EVENT_STATUS: dict[EventType, Callable[[DomainEvent], TransferStatus]] = {
    EventType.TRANSFER_REQUESTED: lambda event: TransferStatus.EN_PROCESO,
    EventType.DEBIT_REJECTED: lambda event: status_for_failure(event.reason),
    EventType.RISK_REJECTED: lambda event: TransferStatus.COMPENSANDO,
    EventType.TRANSFER_FAILED: lambda event: TransferStatus.COMPENSANDO,
    EventType.FUNDS_CREDITED: lambda event: TransferStatus.CONFIRMADO,
    EventType.DEBIT_REVERSED: lambda event: status_for_failure(event.reason),
}


def _status_detail(event: DomainEvent, status: TransferStatus) -> str | None:
    if status is TransferStatus.EN_PROCESO:
        return "Saga coreografiada iniciada: evento publicado en el bus"
    if status is TransferStatus.CONFIRMADO:
        return "Transferencia confirmada: saldo acreditado en la cuenta destino"
    if status is TransferStatus.COMPENSANDO:
        return f"{event.detail} — los servicios compensan de forma autónoma"
    return event.detail


class Projection:
    def __init__(self, db: Database, broadcaster: Broadcaster) -> None:
        self._db = db
        self._broadcaster = broadcaster

    def broadcast(self, transfer_id: str, audit_entries: list[dict]) -> None:
        transfer = snapshot(self._db, transfer_id)
        if transfer is not None:
            self._broadcaster.publish(
                {"type": "transfer", "transfer_id": transfer_id, "transfer": transfer, "audit": audit_entries}
            )

    async def on_telemetry(self, body: bytes) -> None:
        message = TelemetryMessage.model_validate_json(body)
        transfer_id = message.transfer_id
        at = message.at.isoformat()
        with self._db.transaction() as conn:
            if not claim_message(conn, message.message_id):
                return
            if message.kind is TelemetryKind.STEP:
                apply_step(conn, transfer_id, message.step, message.step_status, message.detail)
                entry = add_audit(
                    conn, transfer_id, message.service, AuditCategory.PASO,
                    step=message.step, status=message.step_status, reason=message.reason, detail=message.detail, at=at,
                )
            else:
                apply_status(conn, transfer_id, message.transfer_status, message.reason, message.detail, message.flow_run_id)
                entry = add_audit(
                    conn, transfer_id, message.service, AuditCategory.ESTADO,
                    status=message.transfer_status, reason=message.reason, detail=message.detail, at=at,
                )
        self.broadcast(transfer_id, [entry])

    async def on_event(self, body: bytes) -> None:
        event = DomainEvent.model_validate_json(body)
        transfer_id = event.transfer_id
        with self._db.transaction() as conn:
            if not claim_message(conn, event.event_id):
                return
            entries = [
                add_audit(
                    conn, transfer_id, event.producer, AuditCategory.EVENTO,
                    event_type=event.event_type, reason=event.reason, detail=event.detail,
                    at=event.occurred_at.isoformat(),
                )
            ]
            resolve = EVENT_STATUS.get(event.event_type)
            if resolve is not None:
                status = resolve(event)
                detail = _status_detail(event, status)
                if apply_status(conn, transfer_id, status, event.reason, detail):
                    entries.append(
                        add_audit(conn, transfer_id, SERVICE_NAME, AuditCategory.ESTADO,
                                  status=status, reason=event.reason, detail=detail)
                    )
        self.broadcast(transfer_id, entries)
