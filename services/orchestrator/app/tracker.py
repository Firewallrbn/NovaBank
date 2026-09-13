"""Persistent saga log of the orchestrator (write-ahead) plus telemetry for every state change."""

import json
from datetime import timedelta

from saga_common.contracts import (
    SAGA_STEPS,
    TERMINAL_STATUSES,
    SagaMode,
    StepName,
    StepStatus,
    TransferPayload,
    TransferStatus,
    now_iso,
    utcnow,
)
from saga_common.db import Database
from saga_common.telemetry import Telemetry

SCHEMA = """
CREATE TABLE IF NOT EXISTS sagas (
    transfer_id    TEXT PRIMARY KEY,
    payload        TEXT NOT NULL,
    status         TEXT NOT NULL,
    failure_reason TEXT,
    detail         TEXT,
    flow_run_id    TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saga_steps (
    transfer_id TEXT NOT NULL,
    step        TEXT NOT NULL,
    status      TEXT NOT NULL,
    detail      TEXT,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (transfer_id, step)
);
"""


class SagaTracker:
    def __init__(self, db: Database, telemetry: Telemetry) -> None:
        self._db = db
        self._telemetry = telemetry

    def create(self, payload: TransferPayload) -> bool:
        with self._db.transaction() as conn:
            created = conn.execute(
                "INSERT OR IGNORE INTO sagas (transfer_id, payload, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (payload.transfer_id, payload.model_dump_json(), TransferStatus.PENDIENTE.value, now_iso(), now_iso()),
            ).rowcount == 1
            if created:
                conn.executemany(
                    "INSERT INTO saga_steps (transfer_id, step, status, updated_at) VALUES (?, ?, ?, ?)",
                    [(payload.transfer_id, step.value, StepStatus.PENDING.value, now_iso()) for step in SAGA_STEPS],
                )
        return created

    def get(self, transfer_id: str) -> dict | None:
        saga = self._db.query_one("SELECT * FROM sagas WHERE transfer_id = ?", (transfer_id,))
        return self._serialize(saga) if saga else None

    def recent(self, limit: int) -> list[dict]:
        return [self._serialize(s) for s in self._db.query("SELECT * FROM sagas ORDER BY created_at DESC LIMIT ?", (limit,))]

    def unfinished(self, quiet_seconds: float = 0.0) -> list[dict]:
        """Sagas sin estado final que llevan `quiet_seconds` sin moverse.

        La espera evita adoptar una saga que otro proceso (por ejemplo el Runner
        de Prefect, que ejecuta los flow runs en un subproceso) acaba de arrancar.
        """
        placeholders = ", ".join("?" for _ in TERMINAL_STATUSES)
        cutoff = (utcnow() - timedelta(seconds=quiet_seconds)).isoformat()
        return self._db.query(
            f"SELECT * FROM sagas WHERE status NOT IN ({placeholders}) AND updated_at <= ? ORDER BY created_at",
            (*(s.value for s in TERMINAL_STATUSES), cutoff),
        )

    def step_statuses(self, transfer_id: str) -> dict[StepName, StepStatus]:
        rows = self._db.query("SELECT step, status FROM saga_steps WHERE transfer_id = ?", (transfer_id,))
        return {StepName(r["step"]): StepStatus(r["status"]) for r in rows}

    async def step(
        self,
        transfer_id: str,
        step: StepName,
        status: StepStatus,
        detail: str | None = None,
        reason: str | None = None,
    ) -> None:
        self._db.execute(
            "UPDATE saga_steps SET status = ?, detail = ?, updated_at = ? WHERE transfer_id = ? AND step = ?",
            (status.value, detail, now_iso(), transfer_id, step.value),
        )
        await self._telemetry.step(transfer_id, SagaMode.ORCHESTRATION, step, status, detail=detail, reason=reason)

    async def status(
        self,
        transfer_id: str,
        status: TransferStatus,
        detail: str | None = None,
        reason: str | None = None,
        flow_run_id: str | None = None,
    ) -> None:
        self._db.execute(
            "UPDATE sagas SET status = ?, detail = ?, failure_reason = COALESCE(?, failure_reason), "
            "flow_run_id = COALESCE(?, flow_run_id), updated_at = ? WHERE transfer_id = ?",
            (status.value, detail, reason, flow_run_id, now_iso(), transfer_id),
        )
        await self._telemetry.transfer_status(
            transfer_id, SagaMode.ORCHESTRATION, status, detail=detail, reason=reason, flow_run_id=flow_run_id
        )

    async def skip_pending(self, transfer_id: str) -> None:
        for step, status in self.step_statuses(transfer_id).items():
            if status is StepStatus.PENDING:
                await self.step(transfer_id, step, StepStatus.SKIPPED, detail="Paso omitido: la saga no llegó a esta fase")

    def reset(self) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM saga_steps")
            conn.execute("DELETE FROM sagas")

    def _serialize(self, saga: dict) -> dict:
        steps = self.step_statuses(saga["transfer_id"])
        return {
            **saga,
            "payload": json.loads(saga["payload"]),
            "steps": {step.value: steps[step].value for step in SAGA_STEPS if step in steps},
        }
