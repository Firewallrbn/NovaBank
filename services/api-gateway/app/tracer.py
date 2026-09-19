"""Traza pasiva de la saga coreografiada: dibuja la historia completa como UN solo flow run.

Es un *recolector de trazas*, no un coordinador. Solo registra eventos que ya ocurrieron —el mismo
papel que la bitácora de auditoría—: nunca emite comandos, nunca decide el paso siguiente y nunca
bloquea la saga. Si Prefect está caído, la saga sigue funcionando exactamente igual.

Existe porque en coreografía no hay ningún proceso dueño de la saga, así que Prefect solo puede
mostrar flow runs sueltos. El gateway ya escucha todos los eventos (binding `#`), y es el único sitio
donde la historia completa pasa por un mismo lugar sin introducir acoplamiento entre servicios.
"""

import asyncio
import logging

from prefect import allow_failure, flow, tags, task
from prefect.cache_policies import NO_CACHE
from prefect.states import Completed, Failed, State

from saga_common.contracts import DomainEvent, EventType, TransferStatus, status_for_failure

log = logging.getLogger(__name__)

# Eventos que cierran una saga coreografiada: éxito, rechazo inicial y fin de las compensaciones.
TERMINAL_EVENTS = frozenset(
    {EventType.FUNDS_CREDITED, EventType.DEBIT_REJECTED, EventType.DEBIT_REVERSED}
)

# Eventos de fallo: se pintan en rojo para que el diagrama no mienta sobre lo que pasó.
FAILURE_EVENTS = frozenset(
    {EventType.DEBIT_REJECTED, EventType.RISK_REJECTED, EventType.TRANSFER_FAILED}
)

# Eventos de marcha atrás: mismo vocabulario de estados que usa la saga orquestada.
COMPENSATION_EVENTS = frozenset(
    {EventType.RISK_APPROVAL_REVERTED, EventType.DEBIT_REVERSED}
)

# Si una saga se queda a medias (servicio caído), el trace se cierra solo y no deja tareas colgadas.
IDLE_TIMEOUT_SECONDS = 120.0

_queues: dict[str, asyncio.Queue[DomainEvent]] = {}


@task(cache_policy=NO_CACHE)
async def _event_step(event_type: str, producer: str, detail: str | None) -> State:
    """Un task por evento de dominio: es lo que se ve como cuadrito en el grafo de Prefect.

    El estado que devuelve refleja el **significado de negocio** del evento, no si la grabación
    funcionó: un evento de fallo se pinta en rojo y una compensación como `Compensated`.
    """
    message = detail or f"{producer} → {event_type}"
    if event_type in FAILURE_EVENTS:
        return Failed(name="Rechazado", message=message)
    if event_type in COMPENSATION_EVENTS:
        return Completed(name="Compensated", message=message)
    return Completed(message=message)


def _final_state(event: DomainEvent | None, recorded: int) -> State:
    """El estado del trace es el de la transferencia, no el de la grabación."""
    if event is None:
        return Failed(name="Sin eventos", message="No llegó ningún evento de la saga")
    if event.event_type is EventType.FUNDS_CREDITED:
        return Completed(name=TransferStatus.CONFIRMADO.value, message=f"{recorded} eventos trazados")
    status = status_for_failure(event.reason)
    return Failed(name=status.value, message=event.detail or f"{recorded} eventos trazados")


@flow(name="saga-trace-coreografiada", flow_run_name="saga-{transfer_id}")
async def _trace(transfer_id: str) -> State:
    queue = _queues.get(transfer_id)
    if queue is None:
        return Failed(name="Sin eventos", message="No hay cola de eventos para esta saga")

    recorded = 0
    last: DomainEvent | None = None
    previous = None
    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=IDLE_TIMEOUT_SECONDS)
            # `wait_for` declara la dependencia causal a Prefect: es lo que dibuja la flecha entre
            # un evento y el que lo provocó (la misma relación que lleva `causation_id`).
            # `allow_failure` es imprescindible: tras un evento de fallo vienen las compensaciones,
            # y sin él Prefect las saltaría como `NotReady` — justo lo que hay que demostrar.
            previous = _event_step.with_options(task_run_name=event.event_type.value).submit(
                event.event_type.value,
                event.producer,
                event.detail,
                wait_for=[allow_failure(previous)] if previous is not None else None,
            )
            recorded += 1
            last = event
            if event.event_type in TERMINAL_EVENTS:
                break
    except TimeoutError:
        log.warning("Trace de la saga %s cerrado por inactividad", transfer_id)
        return Failed(name="Saga incompleta", message=f"{recorded} eventos trazados antes del corte")

    # El último task se lanzó con submit(); sin esperarlo, el flow terminaría antes de que cierre
    # y Prefect lo marcaría como `Crashed`. Se espera fuera del bucle de eventos para no bloquearlo.
    if previous is not None:
        try:
            await asyncio.to_thread(previous.wait)
        except Exception:
            log.debug("El último task del trace de %s no cerró limpiamente", transfer_id)
    return _final_state(last, recorded)


class SagaTracer:
    """Alimenta un flow run de Prefect por cada saga coreografiada, sin tocar la saga."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def record(self, event: DomainEvent) -> None:
        transfer_id = event.transfer_id
        queue = _queues.get(transfer_id)

        if queue is None:
            # El trace solo se abre al principio de una saga; un evento suelto no crea un flow run.
            if event.event_type is not EventType.TRANSFER_REQUESTED:
                return
            queue = asyncio.Queue()
            _queues[transfer_id] = queue
            task = asyncio.create_task(self._run(transfer_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        queue.put_nowait(event)

    async def _run(self, transfer_id: str) -> None:
        try:
            with tags(f"transfer:{transfer_id}", "choreography", "saga-trace"):
                await _trace(transfer_id, return_state=True)
        except Exception:
            # La observabilidad nunca debe afectar a la saga: se registra y se sigue.
            log.exception("El trace de la saga %s falló; la saga no se ve afectada", transfer_id)
        finally:
            _queues.pop(transfer_id, None)

    def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        _queues.clear()
