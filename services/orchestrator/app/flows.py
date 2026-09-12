"""Orchestrated saga as a Prefect flow: the orchestrator commands every step and every compensation."""

import asyncio
from collections.abc import Awaitable, Callable

from prefect import flow, task
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
        raise
    except StepUnavailable as exc:
        if retryable:
            await tracker.step(transfer_id, step, StepStatus.RUNNING, detail=f"{exc}. Reintentando…")
        else:
            await tracker.step(
                transfer_id, step, StepStatus.FAILED, detail=str(exc), reason=FailureReason.SERVICE_UNAVAILABLE
            )
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


async def _confirm(transfer: TransferPayload) -> State:
    await credit_destination(transfer)
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
            await COMPENSATIONS[step](transfer)
    await tracker.status(transfer.transfer_id, final_status, detail=detail, reason=reason)
    return Failed(name=final_status.value, message=detail)


@flow(name="transfer-saga-orquestada", flow_run_name="transfer-{transfer_id}")
async def transfer_saga(transfer_id: str, payload: dict) -> State:
    transfer = TransferPayload.model_validate(payload)
    await runtime.tracker.status(
        transfer_id, TransferStatus.EN_PROCESO, detail="Saga orquestada iniciada", flow_run_id=flow_run.id
    )

    completed: list[StepName] = []
    current: StepName | None = None
    try:
        for step, forward in STEPS_BEFORE_PIVOT:
            current = step
            await forward(transfer)
            completed.append(step)
    except StepRejected as exc:
        return await _rollback(transfer, completed, exc.result.reason, str(exc))
    except StepUnavailable as exc:
        if exc.ambiguous and current is not None:
            completed.append(current)
        return await _rollback(transfer, completed, FailureReason.SERVICE_UNAVAILABLE, str(exc))

    return await _confirm(transfer)


_UNDO_ALWAYS = {StepStatus.RUNNING, StepStatus.SUCCEEDED, StepStatus.COMPENSATING}


@flow(name="transfer-saga-recuperacion", flow_run_name="recover-{transfer_id}")
async def recover_saga(transfer_id: str, payload: dict) -> State:
    """Resumes a saga orphaned by an orchestrator crash: forward after the pivot, backward before it."""
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
