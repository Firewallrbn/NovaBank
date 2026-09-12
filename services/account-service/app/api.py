"""HTTP commands used by the orchestrated saga."""

from fastapi import APIRouter, HTTPException, Query, Request

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


@router.get("/accounts")
async def list_accounts(request: Request) -> list[dict]:
    return domain.list_accounts(_db(request))


@router.get("/accounts/{account_id}")
async def get_account(account_id: str, request: Request) -> dict:
    found = _db(request).query_one("SELECT id, owner, balance_cents, updated_at FROM accounts WHERE id = ?", (account_id,))
    if found is None:
        raise HTTPException(404, f"Cuenta {account_id} no encontrada")
    return found


@router.get("/ledger")
async def ledger(
    request: Request,
    account_id: str | None = None,
    transfer_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    return domain.ledger(_db(request), account_id, transfer_id, limit)


@router.post("/accounts/debits")
async def debit(payload: TransferPayload, request: Request):
    with _db(request).transaction() as conn:
        result = domain.debit(conn, payload)
    return respond(result)


@router.post("/accounts/debits/{transfer_id}/refund")
async def refund_debit(transfer_id: str, request: Request):
    with _db(request).transaction() as conn:
        result = domain.refund_debit(conn, transfer_id)
    return respond(result)


@router.post("/accounts/credits")
async def credit(payload: TransferPayload, request: Request):
    with _db(request).transaction() as conn:
        result = domain.credit(conn, payload)
    return respond(result)


@router.post("/admin/reset")
async def reset(request: Request) -> dict:
    store.seed(_db(request), reset=True)
    return {"status": "reset", "service": SERVICE_NAME}
