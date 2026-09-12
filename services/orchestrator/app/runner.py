import asyncio
import json
import logging

from app.flows import recover_saga, transfer_saga
from app.tracker import SagaTracker
from saga_common.contracts import StepStatus

log = logging.getLogger(__name__)


class SagaRunner:
    """Runs sagas in the background and resumes any saga left unfinished (no limbo states)."""

    def __init__(self, tracker: SagaTracker) -> None:
        self._tracker = tracker
        self._active: set[str] = set()
        self._tasks: set[asyncio.Task] = set()

    @property
    def active(self) -> set[str]:
        return set(self._active)

    def start(self, transfer_id: str, payload: dict, recover: bool = False) -> bool:
        if transfer_id in self._active:
            return False
        self._active.add(transfer_id)
        task = asyncio.create_task(self._run(transfer_id, payload, recover))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return True

    async def _run(self, transfer_id: str, payload: dict, recover: bool) -> None:
        saga_flow = recover_saga if recover else transfer_saga
        try:
            await saga_flow(transfer_id=transfer_id, payload=payload, return_state=True)
        except Exception:
            log.exception("La saga %s terminó con error; el bucle de recuperación la retomará", transfer_id)
        finally:
            self._active.discard(transfer_id)

    async def recovery_loop(self, interval: float) -> None:
        while True:
            try:
                for saga in self._tracker.unfinished():
                    transfer_id = saga["transfer_id"]
                    if transfer_id in self._active:
                        continue
                    steps = self._tracker.step_statuses(transfer_id)
                    fresh = all(status is StepStatus.PENDING for status in steps.values())
                    log.warning("Retomando saga %s (%s)", transfer_id, "inicio" if fresh else "recuperación")
                    self.start(transfer_id, json.loads(saga["payload"]), recover=not fresh)
            except Exception:
                log.exception("Error en el bucle de recuperación")
            await asyncio.sleep(interval)
