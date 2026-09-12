import logging

from saga_common.contracts import (
    TELEMETRY_EXCHANGE,
    SagaMode,
    StepName,
    StepStatus,
    TelemetryKind,
    TelemetryMessage,
    TransferStatus,
)
from saga_common.messaging import MessageBus

log = logging.getLogger(__name__)


class Telemetry:
    """Best-effort status feed for the audit log and the real-time UI; never breaks the saga."""

    def __init__(self, bus: MessageBus, service: str) -> None:
        self._bus = bus
        self._service = service

    async def step(
        self,
        transfer_id: str,
        mode: SagaMode,
        step: StepName,
        status: StepStatus,
        detail: str | None = None,
        reason: str | None = None,
    ) -> None:
        await self._send(
            TelemetryMessage(
                kind=TelemetryKind.STEP,
                transfer_id=transfer_id,
                mode=mode,
                service=self._service,
                step=step,
                step_status=status,
                detail=detail,
                reason=reason,
            )
        )

    async def transfer_status(
        self,
        transfer_id: str,
        mode: SagaMode,
        status: TransferStatus,
        detail: str | None = None,
        reason: str | None = None,
        flow_run_id: str | None = None,
    ) -> None:
        await self._send(
            TelemetryMessage(
                kind=TelemetryKind.STATUS,
                transfer_id=transfer_id,
                mode=mode,
                service=self._service,
                transfer_status=status,
                detail=detail,
                reason=reason,
                flow_run_id=flow_run_id,
            )
        )

    async def _send(self, message: TelemetryMessage) -> None:
        try:
            await self._bus.publish(
                TELEMETRY_EXCHANGE,
                f"{message.kind}.{self._service}",
                message.model_dump_json().encode(),
                message.message_id,
            )
        except Exception:
            log.warning("No se pudo publicar telemetría de %s", message.transfer_id, exc_info=True)
