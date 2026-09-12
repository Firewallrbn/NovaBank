"""Hands orchestrated transfers to the orchestrator and retries until it acknowledges them."""

import asyncio
import logging

import httpx

from app.config import DISPATCH_RETRY_SECONDS, ORCHESTRATOR_URL, SERVICE_NAME
from app.projection import Projection
from app.store import AuditCategory, add_audit, payload_from_row
from saga_common.contracts import SagaMode, TransferStatus, now_iso
from saga_common.db import Database

log = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, db: Database, http: httpx.AsyncClient, projection: Projection) -> None:
        self._db = db
        self._http = http
        self._projection = projection

    async def dispatch(self, transfer_id: str, first_attempt: bool = False) -> bool:
        transfer = self._db.query_one("SELECT * FROM transfers WHERE transfer_id = ?", (transfer_id,))
        if transfer is None or transfer["dispatched_at"]:
            return True

        payload = payload_from_row(transfer)
        try:
            response = await self._http.post(f"{ORCHESTRATOR_URL}/sagas", json=payload.model_dump(mode="json"))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("No se pudo despachar %s al orquestador: %s", transfer_id, exc)
            if first_attempt:
                with self._db.transaction() as conn:
                    entry = add_audit(
                        conn, transfer_id, SERVICE_NAME, AuditCategory.DESPACHO,
                        detail="Orquestador no disponible; el despacho se reintentará automáticamente",
                    )
                self._projection.broadcast(transfer_id, [entry])
            return False

        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE transfers SET dispatched_at = ?, updated_at = ? WHERE transfer_id = ? AND dispatched_at IS NULL",
                (now_iso(), now_iso(), transfer_id),
            )
            entry = add_audit(conn, transfer_id, SERVICE_NAME, AuditCategory.DESPACHO, detail="Saga entregada al orquestador")
        self._projection.broadcast(transfer_id, [entry])
        return True

    async def retry_loop(self) -> None:
        while True:
            await asyncio.sleep(DISPATCH_RETRY_SECONDS)
            try:
                pending = self._db.query(
                    "SELECT transfer_id FROM transfers WHERE mode = ? AND dispatched_at IS NULL AND status = ?",
                    (SagaMode.ORCHESTRATION.value, TransferStatus.PENDIENTE.value),
                )
                for item in pending:
                    await self.dispatch(item["transfer_id"])
            except Exception:
                log.exception("Error reintentando despachos pendientes")
