"""Registro del flow de la saga como despliegue permanente de Prefect.

Sin esto, Prefect solo conoce la saga mientras hay un flow run en curso: la
página de Flows aparece vacía en un arranque limpio. Con el despliegue
registrado, `transfer-saga-orquestada` figura siempre en Prefect y además puede
lanzarse desde su UI, porque el orquestador deja corriendo un Runner que atiende
los flow runs que se creen desde allí.
"""

import asyncio
import inspect
import logging

from app import flows
from app.config import DEPLOYMENT_NAME, SERVICE_NAME

log = logging.getLogger(__name__)


async def register(interval_seconds: float) -> asyncio.Task | None:
    """Publica el despliegue y devuelve la tarea del Runner que lo atiende."""
    try:
        deployment = flows.transfer_saga.to_deployment(
            name=DEPLOYMENT_NAME,
            description=(
                "Saga bancaria orquestada de NovaBank. Lanzarla desde aquí ejecuta una "
                "transferencia de demostración con los parámetros por defecto."
            ),
            tags=["novabank", "orquestacion"],
            parameters={"transfer_id": "", "payload": flows.DEMO_PAYLOAD},
        )
        if inspect.isawaitable(deployment):
            deployment = await deployment

        from prefect.runner import Runner

        runner = Runner(name=SERVICE_NAME, query_seconds=interval_seconds)
        await runner.add_deployment(deployment)
        task = asyncio.create_task(runner.start(webserver=False))
        log.info("Despliegue '%s' registrado en Prefect", DEPLOYMENT_NAME)
        return task
    except Exception:
        # La observabilidad no debe tumbar al orquestador: las sagas que dispara
        # el gateway se ejecutan igual, en proceso, con o sin despliegue.
        log.exception("No se pudo registrar el despliegue en Prefect")
        return None
