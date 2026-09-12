"""Choreography: how the Risk service reacts to domain events."""

from app import domain
from saga_common.choreography import Reaction
from saga_common.contracts import EventType, StepName
from saga_common.db import Database


def build_reactions(db: Database) -> list[Reaction]:
    return [
        Reaction(
            on=EventType.FUNDS_DEBITED,
            step=StepName.RISK,
            task_name="evaluate_risk",
            transaction=lambda conn, event: domain.evaluate(conn, event.payload),
            on_success=EventType.RISK_APPROVED,
            on_failure=EventType.RISK_REJECTED,
        ),
        Reaction(
            on=EventType.TRANSFER_FAILED,
            step=StepName.RISK,
            task_name="revert_risk_approval",
            compensation=True,
            transaction=lambda conn, event: domain.revert(conn, event.transfer_id),
            on_success=EventType.RISK_APPROVAL_REVERTED,
        ),
    ]
