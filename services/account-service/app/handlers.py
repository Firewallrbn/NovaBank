"""Choreography: how the Account service reacts to domain events (no coordinator involved)."""

from app import domain
from saga_common.choreography import Reaction
from saga_common.contracts import EventType, StepName
from saga_common.db import Database


def build_reactions(db: Database) -> list[Reaction]:
    return [
        Reaction(
            on=EventType.TRANSFER_REQUESTED,
            step=StepName.DEBIT,
            task_name="debit_source",
            transaction=lambda conn, event: domain.debit(conn, event.payload),
            on_success=EventType.FUNDS_DEBITED,
            on_failure=EventType.DEBIT_REJECTED,
        ),
        Reaction(
            on=EventType.CLEARING_SETTLED,
            step=StepName.CREDIT,
            task_name="credit_destination",
            transaction=lambda conn, event: domain.credit(conn, event.payload),
            on_success=EventType.FUNDS_CREDITED,
        ),
        # Compensations: the refund only happens once Risk has confirmed its own rollback,
        # which keeps the strict reverse order without any coordinator.
        Reaction(
            on=EventType.RISK_REJECTED,
            step=StepName.DEBIT,
            task_name="refund_debit",
            compensation=True,
            transaction=lambda conn, event: domain.refund_debit(conn, event.transfer_id),
            on_success=EventType.DEBIT_REVERSED,
        ),
        Reaction(
            on=EventType.RISK_APPROVAL_REVERTED,
            step=StepName.DEBIT,
            task_name="refund_debit",
            compensation=True,
            transaction=lambda conn, event: domain.refund_debit(conn, event.transfer_id),
            on_success=EventType.DEBIT_REVERSED,
        ),
    ]
