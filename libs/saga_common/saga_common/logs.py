import logging


def configure_logging(service: str) -> None:
    # Importing Prefect reconfigures logging (root and uvicorn at WARNING); force our INFO setup afterwards.
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{service}] %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    uvicorn = logging.getLogger("uvicorn")
    uvicorn.handlers.clear()
    uvicorn.propagate = True
    uvicorn.setLevel(logging.INFO)
    for noisy in ("aio_pika", "aiormq", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
