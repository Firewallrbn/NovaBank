from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

MIN_DELAY_SECONDS = 2.0
MAX_DELAY_SECONDS = 4.0

EVENTS_EXCHANGE = "novabank.events"
TELEMETRY_EXCHANGE = "novabank.telemetry"


def utcnow() -> datetime:
    return datetime.now(UTC)


def now_iso() -> str:
    return utcnow().isoformat()


def format_money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    units, frac = divmod(abs(cents), 100)
    return f"{sign}${units:,}".replace(",", ".") + f",{frac:02d}"


class SagaMode(StrEnum):
    ORCHESTRATION = "orchestration"
    CHOREOGRAPHY = "choreography"


class StepName(StrEnum):
    DEBIT = "DEBIT"
    RISK = "RISK"
    CLEARING = "CLEARING"
    CREDIT = "CREDIT"


SAGA_STEPS: tuple[StepName, ...] = (StepName.DEBIT, StepName.RISK, StepName.CLEARING, StepName.CREDIT)

STEP_LABELS: dict[StepName, str] = {
    StepName.DEBIT: "Débito en cuenta origen",
    StepName.RISK: "Evaluación de riesgo y antifraude",
    StepName.CLEARING: "Liquidación interbancaria",
    StepName.CREDIT: "Crédito en cuenta destino",
}

COMPENSATION_LABELS: dict[StepName, str] = {
    StepName.DEBIT: "Reintegro del débito en cuenta origen",
    StepName.RISK: "Anulación de la aprobación de riesgo",
    StepName.CLEARING: "Anulación de la liquidación interbancaria",
}


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"


# A step status may only move forward in this ranking; late or duplicated updates are ignored.
STEP_STATUS_RANK: dict[StepStatus, int] = {
    StepStatus.PENDING: 0,
    StepStatus.RUNNING: 1,
    StepStatus.SUCCEEDED: 2,
    StepStatus.FAILED: 2,
    StepStatus.SKIPPED: 2,
    StepStatus.COMPENSATING: 3,
    StepStatus.COMPENSATED: 4,
}


class TransferStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN_PROCESO"
    COMPENSANDO = "COMPENSANDO"
    CONFIRMADO = "CONFIRMADO"
    RECHAZADO_FONDOS = "RECHAZADO_FONDOS"
    RECHAZADO_CUENTA = "RECHAZADO_CUENTA"
    RECHAZADO_RIESGO = "RECHAZADO_RIESGO"
    RECHAZADO_RED = "RECHAZADO_RED"
    FALLO_TECNICO = "FALLO_TECNICO"


TERMINAL_STATUSES = frozenset(
    {
        TransferStatus.CONFIRMADO,
        TransferStatus.RECHAZADO_FONDOS,
        TransferStatus.RECHAZADO_CUENTA,
        TransferStatus.RECHAZADO_RIESGO,
        TransferStatus.RECHAZADO_RED,
        TransferStatus.FALLO_TECNICO,
    }
)


class FailureReason(StrEnum):
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    FRAUD_SUSPECTED = "FRAUD_SUSPECTED"
    AMOUNT_LIMIT_EXCEEDED = "AMOUNT_LIMIT_EXCEEDED"
    DAILY_LIMIT_EXCEEDED = "DAILY_LIMIT_EXCEEDED"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    CANCELLED = "CANCELLED"
    RECOVERY_ABORTED = "RECOVERY_ABORTED"


_STATUS_BY_REASON: dict[FailureReason, TransferStatus] = {
    FailureReason.INSUFFICIENT_FUNDS: TransferStatus.RECHAZADO_FONDOS,
    FailureReason.ACCOUNT_NOT_FOUND: TransferStatus.RECHAZADO_CUENTA,
    FailureReason.FRAUD_SUSPECTED: TransferStatus.RECHAZADO_RIESGO,
    FailureReason.AMOUNT_LIMIT_EXCEEDED: TransferStatus.RECHAZADO_RIESGO,
    FailureReason.DAILY_LIMIT_EXCEEDED: TransferStatus.RECHAZADO_RIESGO,
    FailureReason.NETWORK_TIMEOUT: TransferStatus.RECHAZADO_RED,
}


def status_for_failure(reason: str | None) -> TransferStatus:
    try:
        return _STATUS_BY_REASON.get(FailureReason(reason), TransferStatus.FALLO_TECNICO)
    except ValueError:
        return TransferStatus.FALLO_TECNICO


class ChaosConfig(BaseModel):
    force_fraud: bool = False
    clearing_timeout: bool = False


class TransferPayload(BaseModel):
    transfer_id: str
    source_account: str
    destination_account: str
    amount_cents: int = Field(gt=0)
    chaos: ChaosConfig = Field(default_factory=ChaosConfig)
    delay_seconds: float = Field(default=3.0, ge=MIN_DELAY_SECONDS, le=MAX_DELAY_SECONDS)


class OperationStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"
    NOOP = "NOOP"


class OperationResult(BaseModel):
    """Response contract of every local transaction (HTTP command or event handler)."""

    transfer_id: str
    operation: str
    status: OperationStatus
    reason: FailureReason | None = None
    detail: str | None = None
    replayed: bool = False

    @property
    def ok(self) -> bool:
        return self.status is not OperationStatus.REJECTED


class EventType(StrEnum):
    TRANSFER_REQUESTED = "TransferenciaSolicitada"
    FUNDS_DEBITED = "SaldoDebitado"
    DEBIT_REJECTED = "DebitoRechazado"
    RISK_APPROVED = "RiesgoAprobado"
    RISK_REJECTED = "RiesgoRechazado"
    CLEARING_SETTLED = "LiquidacionConfirmada"
    TRANSFER_FAILED = "TransferenciaFallida"
    FUNDS_CREDITED = "SaldoAcreditado"
    RISK_APPROVAL_REVERTED = "AprobacionRiesgoAnulada"
    DEBIT_REVERSED = "DebitoReversado"


class DomainEvent(BaseModel):
    """Choreography event. Carries the full transfer payload so consumers never query other services."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    producer: str
    occurred_at: datetime = Field(default_factory=utcnow)
    payload: TransferPayload
    reason: FailureReason | None = None
    detail: str | None = None
    causation_id: str | None = None

    @property
    def transfer_id(self) -> str:
        return self.payload.transfer_id

    def follow_up(
        self,
        event_type: EventType,
        producer: str,
        reason: FailureReason | None = None,
        detail: str | None = None,
    ) -> "DomainEvent":
        return DomainEvent(
            event_type=event_type,
            producer=producer,
            payload=self.payload,
            reason=reason or self.reason,
            detail=detail,
            causation_id=self.event_id,
        )


class TelemetryKind(StrEnum):
    STEP = "step"
    STATUS = "status"


class TelemetryMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    kind: TelemetryKind
    transfer_id: str
    mode: SagaMode
    service: str
    step: StepName | None = None
    step_status: StepStatus | None = None
    transfer_status: TransferStatus | None = None
    reason: str | None = None
    detail: str | None = None
    flow_run_id: str | None = None
    at: datetime = Field(default_factory=utcnow)


# Declared by every service on startup so no event is ever published to an unbound exchange,
# regardless of container start order.
QUEUE_BINDINGS: dict[str, tuple[str, tuple[str, ...]]] = {
    "account-service.events": (
        EVENTS_EXCHANGE,
        (
            EventType.TRANSFER_REQUESTED,
            EventType.CLEARING_SETTLED,
            EventType.RISK_REJECTED,
            EventType.RISK_APPROVAL_REVERTED,
        ),
    ),
    "risk-service.events": (EVENTS_EXCHANGE, (EventType.FUNDS_DEBITED, EventType.TRANSFER_FAILED)),
    "clearing-service.events": (EVENTS_EXCHANGE, (EventType.RISK_APPROVED,)),
    "api-gateway.projection": (EVENTS_EXCHANGE, ("#",)),
    "api-gateway.telemetry": (TELEMETRY_EXCHANGE, ("#",)),
}
