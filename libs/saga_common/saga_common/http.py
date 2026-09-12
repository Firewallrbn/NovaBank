from fastapi.responses import JSONResponse

from saga_common.contracts import OperationResult


def respond(result: OperationResult, rejected_status: int = 422) -> JSONResponse:
    """200 for success/no-op; business rejections keep a JSON body with status=REJECTED."""
    return JSONResponse(result.model_dump(mode="json"), status_code=200 if result.ok else rejected_status)
