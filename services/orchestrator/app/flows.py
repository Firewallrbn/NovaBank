"""Orchestrated saga as a Prefect flow: the orchestrator commands every step and every compensation."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

from prefect import allow_failure, flow, task
from prefect.cache_policies import NO_CACHE
from prefect.runtime import flow_run
from prefect.states import Completed, Failed, State

from app.clients import BankingClients, StepRejected, StepUnavailable
from app.tracker import SagaTracker
from saga_common.contracts import (
    COMPENSATION_LABELS,
    STEP_LABELS,
    FailureReason,
    OperationResult,
    StepName,
    StepStatus,
    TransferPayload,
    TransferStatus,
    format_money,
    status_for_failure,
)


class _Runtime:
    tracker: SagaTracker
    clients: BankingClients


runtime = _Runtime()

# Última excepción de cada saga, guardada **en memoria del orquestador**.
#
# Los pasos se encadenan con `wait_for` para que Prefect dibuje el grafo de la saga, y eso obliga a
# leer el resultado del task como estado en vez de como excepción. El problema es que una excepción
# que viaja por el estado de Prefect se serializa y vuelve como otro objeto: el `except StepRejected`
# dejaría de reconocerla y la saga acabaría en FALLO_TECNICO en vez de clasificar el rechazo.
# Por eso la referencia original se conserva aquí: la clasificación de estados nunca depende de lo
# que Prefect deserialice.
_step_errors: dict[str, Exception] = {}


def _chain(previous):
    """Declara la dependencia con el paso anterior; `allow_failure` permite encadenar las
    compensaciones detrás del paso que falló, que es justo lo que hay que poder ver."""
    return [allow_failure(previous)] if previous is not None else None


def _raise_recorded(transfer_id: str, fallback: str) -> None:
    raise _step_errors.pop(transfer_id, None) or StepUnavailable(fallback, ambiguous=True)


async def ensure_runtime() -> None:
    """Prepara las dependencias del flow si nadie las inyectó todavía.

    El servicio las inyecta al arrancar, pero Prefect ejecuta los flow runs de un
    despliegue en un subproceso propio: allí este módulo se importa de cero y hay
    que construirlas otra vez para que la saga lanzada desde Prefect funcione.
    """
    if getattr(runtime, "tracker", None) is not None:
        return

    import httpx

    from app.config import DB_PATH, HTTP_TIMEOUT_SECONDS, RABBITMQ_URL, SERVICE_NAME
    from app.tracker import SCHEMA
    from saga_common.db import Database
    from saga_common.messaging import MessageBus
    from saga_common.telemetry import Telemetry

    bus = MessageBus(RABBITMQ_URL)
    await bus.connect()
    runtime.tracker = SagaTracker(Database(DB_PATH, SCHEMA), Telemetry(bus, SERVICE_NAME))
    runtime.clients = BankingClients(httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS))


async def _run_forward(
    step: StepName,
    transfer: TransferPayload,
    call: Callable[[TransferPayload], Awaitable[OperationResult]],
    retryable: bool = False,
) -> OperationResult:
    tracker = runtime.tracker
    transfer_id = transfer.transfer_id
    # Write-ahead: the step is logged as RUNNING before the command is sent, so recovery knows it may have run.
    await tracker.step(transfer_id, step, StepStatus.RUNNING, detail=STEP_LABELS[step])
    await asyncio.sleep(transfer.delay_seconds)
    try:
        result = await call(transfer)
    except StepRejected as exc:
        await tracker.step(transfer_id, step, StepStatus.FAILED, detail=str(exc), reason=exc.result.reason)
        _step_errors[transfer_id] = exc
        raise
    except StepUnavailable as exc:
        if retryable:
            await tracker.step(transfer_id, step, StepStatus.RUNNING, detail=f"{exc}. Reintentando…")
        else:
            await tracker.step(
                transfer_id, step, StepStatus.FAILED, detail=str(exc), reason=FailureReason.SERVICE_UNAVAILABLE
            )
        _step_errors[transfer_id] = exc
        raise
    await tracker.step(transfer_id, step, StepStatus.SUCCEEDED, detail=result.detail)
    return result


async def _run_compensation(
    step: StepName,
    transfer: TransferPayload,
    call: Callable[[str], Awaitable[OperationResult]],
) -> State:
    tracker = runtime.tracker
    await tracker.step(transfer.transfer_id, step, StepStatus.COMPENSATING, detail=COMPENSATION_LABELS[step])
    await asyncio.sleep(transfer.delay_seconds)
    result = await call(transfer.transfer_id)
    await tracker.step(transfer.transfer_id, step, StepStatus.COMPENSATED, detail=result.detail)
    return Completed(name="Compensated", message=result.detail)


@task(name="debit_source", cache_policy=NO_CACHE)
async def debit_source(transfer: TransferPayload) -> OperationResult:
    return await _run_forward(StepName.DEBIT, transfer, runtime.clients.debit)


@task(name="evaluate_risk", cache_policy=NO_CACHE)
async def evaluate_risk(transfer: TransferPayload) -> OperationResult:
    return await _run_forward(StepName.RISK, transfer, runtime.clients.evaluate_risk)


@task(name="settle_clearing", cache_policy=NO_CACHE)
async def settle_clearing(transfer: TransferPayload) -> OperationResult:
    return await _run_forward(StepName.CLEARING, transfer, runtime.clients.settle)


# After the pivot (clearing) the saga can only move forward, so crediting retries until it succeeds.
@task(name="credit_destination", cache_policy=NO_CACHE, retries=10, retry_delay_seconds=3)
async def credit_destination(transfer: TransferPayload) -> OperationResult:
    return await _run_forward(StepName.CREDIT, transfer, runtime.clients.credit, retryable=True)


@task(name="refund_debit", cache_policy=NO_CACHE, retries=5, retry_delay_seconds=2)
async def refund_debit(transfer: TransferPayload) -> State:
    return await _run_compensation(StepName.DEBIT, transfer, runtime.clients.refund_debit)


@task(name="revert_risk_approval", cache_policy=NO_CACHE, retries=5, retry_delay_seconds=2)
async def revert_risk_approval(transfer: TransferPayload) -> State:
    return await _run_compensation(StepName.RISK, transfer, runtime.clients.revert_risk)


@task(name="cancel_settlement", cache_policy=NO_CACHE, retries=5, retry_delay_seconds=2)
async def cancel_settlement(transfer: TransferPayload) -> State:
    return await _run_compensation(StepName.CLEARING, transfer, runtime.clients.cancel_settlement)


STEPS_BEFORE_PIVOT = (
    (StepName.DEBIT, debit_source),
    (StepName.RISK, evaluate_risk),
    (StepName.CLEARING, settle_clearing),
)

COMPENSATIONS = {
    StepName.DEBIT: refund_debit,
    StepName.RISK: revert_risk_approval,
    StepName.CLEARING: cancel_settlement,
}


async def _confirm(transfer: TransferPayload, previous=None) -> State:
    state = await credit_destination(transfer, return_state=True, wait_for=_chain(previous))
    if state.is_failed() or state.is_crashed():
        _raise_recorded(transfer.transfer_id, "El crédito en destino no pudo completarse")
    detail = (
        f"Transferencia de {format_money(transfer.amount_cents)} de {transfer.source_account} "
        f"a {transfer.destination_account} confirmada"
    )
    await runtime.tracker.status(transfer.transfer_id, TransferStatus.CONFIRMADO, detail=detail)
    return Completed(name=TransferStatus.CONFIRMADO.value, message=detail)


async def _rollback(
    transfer: TransferPayload,
    to_compensate: list[StepName],
    reason: FailureReason | None,
    detail: str,
    previous=None,
) -> State:
    tracker = runtime.tracker
    final_status = status_for_failure(reason)
    await tracker.skip_pending(transfer.transfer_id)
    if to_compensate:
        order = " → ".join(COMPENSATION_LABELS[step] for step in reversed(to_compensate))
        await tracker.status(
            transfer.transfer_id, TransferStatus.COMPENSANDO, detail=f"Compensando en orden inverso: {order}", reason=reason
        )
        for step in reversed(to_compensate):
            previous = await COMPENSATIONS[step](transfer, return_state=True, wait_for=_chain(previous))
            if previous.is_failed() or previous.is_crashed():
                # Se propaga para que el bucle de recuperación retome la saga, igual que antes.
                raise RuntimeError(f"La compensación de {step.value} no pudo completarse")
    await tracker.status(transfer.transfer_id, final_status, detail=detail, reason=reason)
    return Failed(name=final_status.value, message=detail)


# Parámetros por defecto del despliegue: permiten lanzar una saga desde la propia
# UI de Prefect sin pasar por el gateway, útil para inspeccionar el flow a solas.
DEMO_PAYLOAD = {
    "source_account": "ACC-001",
    "destination_account": "ACC-002",
    "amount_cents": 5_000_000,
    "chaos": {"force_fraud": False, "clearing_timeout": False},
    "delay_seconds": 2.0,
}


@flow(name="transfer-saga-orquestada", flow_run_name="transfer-{transfer_id}")
async def transfer_saga(transfer_id: str = "", payload: dict | None = None) -> State:
    await ensure_runtime()
    transfer_id = transfer_id or str(uuid4())
    transfer = TransferPayload.model_validate({**(payload or DEMO_PAYLOAD), "transfer_id": transfer_id})
    # El saga log es idempotente: la saga puede venir del gateway o de un disparo
    # manual desde Prefect, y en ambos casos queda registrada aquí.
    runtime.tracker.create(transfer)
    await runtime.tracker.status(
        transfer_id, TransferStatus.EN_PROCESO, detail="Saga orquestada iniciada", flow_run_id=flow_run.id
    )

    completed: list[StepName] = []
    current: StepName | None = None
    previous = None
    _step_errors.pop(transfer_id, None)
    try:
        for step, forward in STEPS_BEFORE_PIVOT:
            current = step
            # `previous` se asigna antes de comprobar el fallo: así las compensaciones se encadenan
            # detrás del paso que falló y no detrás del último que salió bien.
            previous = await forward(transfer, return_state=True, wait_for=_chain(previous))
            if previous.is_failed() or previous.is_crashed():
                _raise_recorded(transfer_id, f"El paso {step.value} no devolvió resultado")
            completed.append(step)
    except StepRejected as exc:
        return await _rollback(transfer, completed, exc.result.reason, str(exc), previous)
    except StepUnavailable as exc:
        if exc.ambiguous and current is not None:
            completed.append(current)
        return await _rollback(transfer, completed, FailureReason.SERVICE_UNAVAILABLE, str(exc), previous)

    return await _confirm(transfer, previous)


_UNDO_ALWAYS = {StepStatus.RUNNING, StepStatus.SUCCEEDED, StepStatus.COMPENSATING}


@flow(name="transfer-saga-recuperacion", flow_run_name="recover-{transfer_id}")
async def recover_saga(transfer_id: str, payload: dict) -> State:
    """Resumes a saga orphaned by an orchestrator crash: forward after the pivot, backward before it."""
    await ensure_runtime()
    transfer = TransferPayload.model_validate(payload)
    tracker = runtime.tracker
    saga = tracker.get(transfer_id) or {}
    steps = tracker.step_statuses(transfer_id)

    if steps.get(StepName.CLEARING) is StepStatus.SUCCEEDED:
        await tracker.status(
            transfer_id, TransferStatus.EN_PROCESO,
            detail="Recuperación hacia adelante: la liquidación ya ocurrió, se completa el crédito",
            flow_run_id=flow_run.id,
        )
        return await _confirm(transfer)

    reason = saga.get("failure_reason") or FailureReason.RECOVERY_ABORTED
    business_failure = reason not in (FailureReason.SERVICE_UNAVAILABLE, FailureReason.RECOVERY_ABORTED)
    undo = _UNDO_ALWAYS if business_failure else _UNDO_ALWAYS | {StepStatus.FAILED}
    to_compensate = [step for step, _ in STEPS_BEFORE_PIVOT if steps.get(step) in undo]
    await tracker.status(
        transfer_id, TransferStatus.COMPENSANDO,
        detail="Recuperación hacia atrás tras reinicio del orquestador", reason=reason, flow_run_id=flow_run.id,
    )
    detail = saga.get("detail") if business_failure else "Saga interrumpida por reinicio del orquestador; pasos ejecutados compensados"
    return await _rollback(transfer, to_compensate, FailureReason(reason), detail or "Saga compensada en recuperación")
