"""HTTP commands the orchestrator sends to the domain services."""

import httpx

from app.config import ACCOUNT_URL, CLEARING_URL, RISK_URL
from saga_common.contracts import OperationResult, OperationStatus, TransferPayload


class StepRejected(Exception):
    """Definitive business rejection: the step did not happen and needs no compensation."""

    def __init__(self, result: OperationResult) -> None:
        super().__init__(result)
        self.result = result

    def __str__(self) -> str:
        return self.result.detail or str(self.result.reason)


class StepUnavailable(Exception):
    """Transport failure. `ambiguous` means the step may have run, so it must be compensated too."""

    def __init__(self, message: str, ambiguous: bool) -> None:
        super().__init__(message, ambiguous)
        self.message = message
        self.ambiguous = ambiguous

    def __str__(self) -> str:
        return self.message


class BankingClients:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def _post(self, url: str, body: dict | None = None) -> OperationResult:
        try:
            response = await self._http.post(url, json=body)
        except httpx.ConnectError as exc:
            raise StepUnavailable(f"Servicio no disponible ({url})", ambiguous=False) from exc
        except httpx.HTTPError as exc:
            raise StepUnavailable(f"Sin respuesta de {url}: resultado incierto", ambiguous=True) from exc

        try:
            data = response.json()
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get("status") == OperationStatus.REJECTED:
            raise StepRejected(OperationResult.model_validate(data))
        if response.status_code >= 400 or not isinstance(data, dict):
            raise StepUnavailable(
                f"Error HTTP {response.status_code} en {url}", ambiguous=response.status_code >= 500
            )
        return OperationResult.model_validate(data)

    async def debit(self, payload: TransferPayload) -> OperationResult:
        return await self._post(f"{ACCOUNT_URL}/accounts/debits", payload.model_dump(mode="json"))

    async def refund_debit(self, transfer_id: str) -> OperationResult:
        return await self._post(f"{ACCOUNT_URL}/accounts/debits/{transfer_id}/refund")

    async def credit(self, payload: TransferPayload) -> OperationResult:
        return await self._post(f"{ACCOUNT_URL}/accounts/credits", payload.model_dump(mode="json"))

    async def evaluate_risk(self, payload: TransferPayload) -> OperationResult:
        return await self._post(f"{RISK_URL}/risk/evaluations", payload.model_dump(mode="json"))

    async def revert_risk(self, transfer_id: str) -> OperationResult:
        return await self._post(f"{RISK_URL}/risk/evaluations/{transfer_id}/revert")

    async def settle(self, payload: TransferPayload) -> OperationResult:
        return await self._post(f"{CLEARING_URL}/clearing/settlements", payload.model_dump(mode="json"))

    async def cancel_settlement(self, transfer_id: str) -> OperationResult:
        return await self._post(f"{CLEARING_URL}/clearing/settlements/{transfer_id}/cancel")
