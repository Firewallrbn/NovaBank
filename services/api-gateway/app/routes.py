import asyncio
import hashlib
import json
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from app.config import (
    ACCOUNT_URL,
    CLEARING_URL,
    ORCHESTRATOR_URL,
    PREFECT_API_URL,
    PREFECT_UI_URL,
    RABBITMQ_UI_URL,
    RISK_URL,
    SERVICE_NAME,
)
from app.store import (
    AuditCategory,
    add_audit,
    audit_for,
    in_flight_count,
    insert_transfer,
    list_transfers,
    recent_audit,
    reset,
    snapshot,
)
from app.stream import sse_events
from saga_common.contracts import (
    MAX_DELAY_SECONDS,
    MIN_DELAY_SECONDS,
    ChaosConfig,
    DomainEvent,
    EventType,
    SagaMode,
    TransferPayload,
    TransferStatus,
    format_money,
    now_iso,
)
from saga_common.db import row
from saga_common.outbox import enqueue_event

router = APIRouter(prefix="/api")

MODE_LABELS = {SagaMode.ORCHESTRATION: "orquestación", SagaMode.CHOREOGRAPHY: "coreografía"}


class TransferRequest(BaseModel):
    source_account: str = Field(min_length=1, max_length=40)
    destination_account: str = Field(min_length=1, max_length=40)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    mode: SagaMode = SagaMode.ORCHESTRATION
    chaos: ChaosConfig = Field(default_factory=ChaosConfig)
    delay_seconds: float = Field(default=3.0, ge=MIN_DELAY_SECONDS, le=MAX_DELAY_SECONDS)

    @model_validator(mode="after")
    def _distinct_accounts(self) -> "TransferRequest":
        if self.source_account == self.destination_account:
            raise ValueError("La cuenta origen y la cuenta destino deben ser distintas")
        return self


def _parse_key(raw: str | None) -> str:
    if raw is None:
        return str(uuid4())
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise HTTPException(400, "Idempotency-Key debe ser un UUID válido") from exc


@router.get("/config")
async def config() -> dict:
    return {
        "prefect_ui_url": PREFECT_UI_URL,
        "rabbitmq_ui_url": RABBITMQ_UI_URL,
        "min_delay_seconds": MIN_DELAY_SECONDS,
        "max_delay_seconds": MAX_DELAY_SECONDS,
        "modes": [mode.value for mode in SagaMode],
    }


@router.post("/idempotency-keys", status_code=201)
async def issue_idempotency_key() -> dict:
    return {"idempotency_key": str(uuid4())}


@router.post("/transfers")
async def create_transfer(
    body: TransferRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None),
) -> JSONResponse:
    state = request.app.state
    key = _parse_key(idempotency_key)
    request_hash = hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    payload = TransferPayload(
        transfer_id=key,
        source_account=body.source_account,
        destination_account=body.destination_account,
        amount_cents=int((body.amount * 100).to_integral_value()),
        chaos=body.chaos,
        delay_seconds=body.delay_seconds,
    )

    conflict = duplicate = False
    entries: list[dict] = []
    with state.db.transaction() as conn:
        existing = row(conn, "SELECT request_hash FROM transfers WHERE transfer_id = ?", (key,))
        if existing is not None and existing["request_hash"] != request_hash:
            conflict = True
        elif existing is not None:
            duplicate = True
            conn.execute(
                "UPDATE transfers SET duplicate_requests = duplicate_requests + 1, updated_at = ? WHERE transfer_id = ?",
                (now_iso(), key),
            )
            entries.append(add_audit(
                conn, key, SERVICE_NAME, AuditCategory.DUPLICADO,
                detail="Reintento con la misma Idempotency-Key: se devuelve la operación original sin ejecutar un nuevo cobro",
            ))
        else:
            insert_transfer(conn, payload, body.mode, request_hash)
            entries.append(add_audit(
                conn, key, SERVICE_NAME, AuditCategory.SOLICITUD, status=TransferStatus.PENDIENTE,
                detail=(
                    f"Solicitud de transferencia de {format_money(payload.amount_cents)} de {payload.source_account} "
                    f"a {payload.destination_account} ({MODE_LABELS[body.mode]})"
                ),
            ))
            if body.mode is SagaMode.CHOREOGRAPHY:
                enqueue_event(conn, DomainEvent(event_type=EventType.TRANSFER_REQUESTED, producer=SERVICE_NAME, payload=payload))

    if conflict:
        raise HTTPException(422, "La Idempotency-Key ya fue usada con datos distintos")

    state.projection.broadcast(key, entries)
    if not duplicate:
        if body.mode is SagaMode.CHOREOGRAPHY:
            state.relay.notify()
        else:
            await state.dispatcher.dispatch(key, first_attempt=True)

    return JSONResponse(
        {"duplicate": duplicate, "idempotency_key": key, "transfer": snapshot(state.db, key)},
        status_code=200 if duplicate else 202,
        headers={"Idempotency-Key": key, "Idempotency-Replayed": str(duplicate).lower()},
    )


@router.get("/transfers")
async def get_transfers(request: Request, limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    return list_transfers(request.app.state.db, limit)


@router.get("/transfers/{transfer_id}")
async def get_transfer(transfer_id: str, request: Request) -> dict:
    db = request.app.state.db
    transfer = snapshot(db, transfer_id)
    if transfer is None:
        raise HTTPException(404, f"Transferencia {transfer_id} no encontrada")
    return {**transfer, "audit": audit_for(db, transfer_id)}


@router.get("/transfers/{transfer_id}/audit")
async def get_transfer_audit(transfer_id: str, request: Request) -> list[dict]:
    return audit_for(request.app.state.db, transfer_id)


@router.get("/audit")
async def get_audit(request: Request, limit: int = Query(200, ge=1, le=1000)) -> list[dict]:
    return recent_audit(request.app.state.db, limit)


@router.get("/stream")
async def stream(request: Request, transfer_id: str | None = None) -> StreamingResponse:
    state = request.app.state
    initial = None
    if transfer_id and (transfer := snapshot(state.db, transfer_id)) is not None:
        initial = {"type": "transfer", "transfer_id": transfer_id, "transfer": transfer, "audit": []}
    return StreamingResponse(
        sse_events(request, state.broadcaster, transfer_id, initial),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _proxy_get(request: Request, url: str, params: dict | None = None) -> JSONResponse:
    try:
        response = await request.app.state.http.get(url, params=params)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"Servicio no disponible: {url}") from exc
    return JSONResponse(response.json(), status_code=response.status_code)


@router.get("/accounts")
async def get_accounts(request: Request) -> JSONResponse:
    return await _proxy_get(request, f"{ACCOUNT_URL}/accounts")


@router.get("/accounts/{account_id}/ledger")
async def get_ledger(account_id: str, request: Request) -> JSONResponse:
    return await _proxy_get(request, f"{ACCOUNT_URL}/ledger", {"account_id": account_id})


@router.get("/risk/limits/{account_id}")
async def get_risk_limits(account_id: str, request: Request) -> JSONResponse:
    return await _proxy_get(request, f"{RISK_URL}/risk/limits/{account_id}")


async def _check(http: httpx.AsyncClient, url: str) -> str:
    try:
        response = await http.get(url, timeout=2)
        return "ok" if response.status_code == 200 else f"error {response.status_code}"
    except httpx.HTTPError:
        return "caído"


@router.get("/services/health")
async def services_health(request: Request) -> dict:
    targets = {
        "account-service": f"{ACCOUNT_URL}/health",
        "risk-service": f"{RISK_URL}/health",
        "clearing-service": f"{CLEARING_URL}/health",
        "orchestrator": f"{ORCHESTRATOR_URL}/health",
        "prefect": f"{PREFECT_API_URL}/health",
    }
    http = request.app.state.http
    results = await asyncio.gather(*(_check(http, url) for url in targets.values()))
    return {SERVICE_NAME: "ok", **dict(zip(targets, results))}


@router.post("/admin/reset")
async def reset_all(request: Request) -> dict:
    state = request.app.state
    if in_flight_count(state.db):
        raise HTTPException(409, "Hay transferencias en curso; espere a que terminen para reiniciar")
    try:
        response = await state.http.post(f"{ORCHESTRATOR_URL}/admin/reset")
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Orquestador no disponible") from exc
    if response.status_code != 200:
        raise HTTPException(response.status_code, response.json().get("detail", "No se pudo reiniciar el orquestador"))

    services = {"orchestrator": True}
    for name, base_url in (("account-service", ACCOUNT_URL), ("risk-service", RISK_URL), ("clearing-service", CLEARING_URL)):
        try:
            services[name] = (await state.http.post(f"{base_url}/admin/reset")).status_code == 200
        except httpx.HTTPError:
            services[name] = False
    reset(state.db)
    state.broadcaster.publish({"type": "reset", "transfer_id": None})
    return {"status": "reset", "services": services}
