"""HTTP commands used by the orchestrated saga."""

from fastapi import APIRouter, Query, Request

from app import domain, store
from app.config import SERVICE_NAME
from saga_common.contracts import TransferPayload
from saga_common.db import Database
from saga_common.http import respond

router = APIRouter()


def _db(request: Request) -> Database:
    return request.app.state.db


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/risk/evaluations")
async def list_evaluations(request: Request, limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    return domain.list_evaluations(_db(request), limit)


@router.get("/risk/limits/{account_id}")
async def limits(account_id: str, request: Request) -> dict:
    return domain.limits(_db(request), account_id)


@router.post("/risk/evaluations")
async def evaluate(payload: TransferPayload, request: Request):
    with _db(request).transaction() as conn:
        result = domain.evaluate(conn, payload)
    return respond(result)


@router.post("/risk/evaluations/{transfer_id}/revert")
async def revert(transfer_id: str, request: Request):
    with _db(request).transaction() as conn:
        result = domain.revert(conn, transfer_id)
    return respond(result)


@router.post("/admin/reset")
async def reset(request: Request) -> dict:
    store.reset(_db(request))
    return {"status": "reset", "service": SERVICE_NAME}
