from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.config import SERVICE_NAME
from app.runner import SagaRunner
from app.tracker import SagaTracker
from saga_common.contracts import TransferPayload

router = APIRouter()


def _tracker(request: Request) -> SagaTracker:
    return request.app.state.tracker


def _runner(request: Request) -> SagaRunner:
    return request.app.state.runner


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME}


@router.post("/sagas")
async def start_saga(payload: TransferPayload, request: Request) -> JSONResponse:
    tracker = _tracker(request)
    created = tracker.create(payload)
    if created:
        _runner(request).start(payload.transfer_id, payload.model_dump(mode="json"))
    return JSONResponse({"created": created, **tracker.get(payload.transfer_id)}, status_code=202 if created else 200)


@router.get("/sagas")
async def list_sagas(request: Request, limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    return _tracker(request).recent(limit)


@router.get("/sagas/{transfer_id}")
async def get_saga(transfer_id: str, request: Request) -> dict:
    saga = _tracker(request).get(transfer_id)
    if saga is None:
        raise HTTPException(404, f"Saga {transfer_id} no encontrada")
    return saga


@router.post("/admin/reset")
async def reset(request: Request) -> dict:
    if _runner(request).active:
        raise HTTPException(409, "Hay sagas en ejecución; espere a que terminen para reiniciar")
    _tracker(request).reset()
    return {"status": "reset", "service": SERVICE_NAME}
