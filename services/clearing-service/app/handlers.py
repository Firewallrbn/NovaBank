"""Choreography: how the Clearing Gateway reacts to domain events."""

from app import domain
from saga_common.choreography import Reaction
from saga_common.contracts import EventType, StepName
from saga_common.db import Database


def build_reactions(db: Database) -> list[Reaction]:
    return [
        Reaction(
            on=EventType.RISK_APPROVED,
            step=StepName.CLEARING,
            task_name="settle_clearing",
            prepare=lambda event: domain.contact_network(db, event.payload),
            transaction=lambda conn, event: domain.finalize(conn, event.payload),
            on_success=EventType.CLEARING_SETTLED,
            on_failure=EventType.TRANSFER_FAILED,
        ),
    ]
