"""Choreography participant: reacts to domain events with a local transaction and emits the next event.

There is no coordinator. Each service declares a table of `Reaction`s; every reaction runs inside
its own Prefect flow (tagged with the transfer id) so the chain is traceable in Prefect UI.
"""

import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from prefect import flow, tags, task
from prefect.cache_policies import NO_CACHE
from prefect.states import Completed, Failed, State

from saga_common import inbox
from saga_common.contracts import (
    COMPENSATION_LABELS,
    STEP_LABELS,
    DomainEvent,
    EventType,
    OperationResult,
    OperationStatus,
    SagaMode,
    StepName,
    StepStatus,
)
from saga_common.db import Database
from saga_common.messaging import MessageBus
from saga_common.outbox import OutboxRelay, enqueue_event
from saga_common.telemetry import Telemetry

log = logging.getLogger(__name__)

LocalTransaction = Callable[[sqlite3.Connection, DomainEvent], OperationResult]
Preparation = Callable[[DomainEvent], Awaitable[None]]


@dataclass(frozen=True)
class Reaction:
    on: EventType
    step: StepName
    task_name: str
    transaction: LocalTransaction
    on_success: EventType
    on_failure: EventType | None = None
    compensation: bool = False
    prepare: Preparation | None = None


class StepRejected(Exception):
    def __init__(self, result: OperationResult) -> None:
        super().__init__(result)
        self.result = result

    def __str__(self) -> str:
        return self.result.detail or str(self.result.reason)


class Participant:
    def __init__(
        self,
        service: str,
        db: Database,
        relay: OutboxRelay,
        telemetry: Telemetry,
        reactions: list[Reaction],
    ) -> None:
        self._service = service
        self._db = db
        self._relay = relay
        self._telemetry = telemetry
        self._reactions = {reaction.on: reaction for reaction in reactions}
        self._flows = {reaction.on: self._build_flow(reaction) for reaction in reactions}

    async def handle(self, body: bytes) -> None:
        event = DomainEvent.model_validate_json(body)
        if event.event_type not in self._reactions:
            return
        if inbox.is_processed(self._db, event.event_id, self._service):
            log.info("Evento %s duplicado; ya fue procesado", event.event_id)
            return

        with tags(f"transfer:{event.transfer_id}", "choreography", self._service):
            await self._flows[event.event_type](
                transfer_id=event.transfer_id,
                event=event.model_dump(mode="json"),
                return_state=True,
            )

        if not inbox.is_processed(self._db, event.event_id, self._service):
            raise RuntimeError(f"La transacción local para {event.event_type} no se confirmó; se reintentará")

    def _build_flow(self, reaction: Reaction):
        local_task = task(name=reaction.task_name, cache_policy=NO_CACHE)(self._make_task(reaction))

        async def react(transfer_id: str, event: dict) -> State:
            domain_event = DomainEvent.model_validate(event)
            try:
                result = await local_task(domain_event)
            except StepRejected as exc:
                return Failed(name="Rechazado", message=exc.result.detail)
            name = "Compensated" if reaction.compensation else "Completed"
            return Completed(name=name, message=result.detail)

        return flow(
            name=f"{self._service}.{reaction.on.value}",
            flow_run_name=f"{reaction.task_name}-{{transfer_id}}",
        )(react)

    def _make_task(self, reaction: Reaction):
        async def run_local_transaction(event: DomainEvent) -> OperationResult:
            payload = event.payload
            label = COMPENSATION_LABELS[reaction.step] if reaction.compensation else STEP_LABELS[reaction.step]
            active = StepStatus.COMPENSATING if reaction.compensation else StepStatus.RUNNING
            await self._telemetry.step(
                payload.transfer_id,
                SagaMode.CHOREOGRAPHY,
                reaction.step,
                active,
                detail=f"{label} (reacciona a {event.event_type.value})",
            )
            await asyncio.sleep(payload.delay_seconds)
            if reaction.prepare is not None:
                await reaction.prepare(event)

            with self._db.transaction() as conn:
                if not inbox.claim(conn, event.event_id, self._service):
                    return OperationResult(
                        transfer_id=payload.transfer_id,
                        operation=reaction.task_name,
                        status=OperationStatus.NOOP,
                        detail="Evento duplicado ignorado",
                        replayed=True,
                    )
                result = reaction.transaction(conn, event)
                if not result.ok and reaction.on_failure is None:
                    raise RuntimeError(f"{reaction.task_name} es reintentable y falló: {result.detail}")
                next_type = reaction.on_success if result.ok else reaction.on_failure
                enqueue_event(conn, event.follow_up(next_type, self._service, reason=result.reason, detail=result.detail))
            self._relay.notify()

            if reaction.compensation:
                done = StepStatus.COMPENSATED
            else:
                done = StepStatus.SUCCEEDED if result.ok else StepStatus.FAILED
            await self._telemetry.step(
                payload.transfer_id,
                SagaMode.CHOREOGRAPHY,
                reaction.step,
                done,
                detail=result.detail,
                reason=result.reason,
            )
            if not result.ok:
                raise StepRejected(result)
            return result

        return run_local_transaction


@asynccontextmanager
async def run_participant(
    service: str,
    queue: str,
    db: Database,
    rabbitmq_url: str,
    reactions: list[Reaction],
) -> AsyncIterator[None]:
    bus = MessageBus(rabbitmq_url)
    await bus.connect()
    relay = OutboxRelay(db, bus)
    participant = Participant(service, db, relay, Telemetry(bus, service), reactions)
    relay_task = asyncio.create_task(relay.run())
    await bus.subscribe(queue, participant.handle)
    try:
        yield
    finally:
        relay_task.cancel()
        await bus.close()
