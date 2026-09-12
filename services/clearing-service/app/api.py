"""HTTP commands used by the orchestrated saga."""

from fastapi import APIRouter, Query, Request

from app import domain, store
from app.config import SERVICE_NAME
from saga_common.contracts import FailureReason, TransferPayload
from saga_common.db import Database
from saga_common.http import respond

router = APIRouter()


def _db(request: Request) -> Database:
    return request.app.state.db


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/clearing/settlements")
async def list_settlements(request: Request, limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    return domain.list_settlements(_db(request), limit)


@router.post("/clearing/settlements")
async def settle(payload: TransferPayload, request: Request):
    db = _db(request)
    await domain.contact_network(db, payload)
    with db.transaction() as conn:
        result = domain.finalize(conn, payload)
    return respond(result, rejected_status=504 if result.reason is FailureReason.NETWORK_TIMEOUT else 422)


@router.post("/clearing/settlements/{transfer_id}/cancel")
async def cancel(transfer_id: str, request: Request):
    with _db(request).transaction() as conn:
        result = domain.cancel(conn, transfer_id)
    return respond(result)


@router.post("/admin/reset")
async def reset(request: Request) -> dict:
    store.reset(_db(request))
    return {"status": "reset", "service": SERVICE_NAME}
