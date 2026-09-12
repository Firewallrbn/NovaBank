import os

SERVICE_NAME = "clearing-service"
QUEUE_NAME = "clearing-service.events"
DB_PATH = os.getenv("DB_PATH", "/data/clearing.db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

NETWORK_TIMEOUT_SECONDS = float(os.getenv("CLEARING_NETWORK_TIMEOUT_SECONDS", "3"))
