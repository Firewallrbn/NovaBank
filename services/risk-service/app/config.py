import os

SERVICE_NAME = "risk-service"
QUEUE_NAME = "risk-service.events"
DB_PATH = os.getenv("DB_PATH", "/data/risk.db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

MAX_SINGLE_TRANSFER_CENTS = int(os.getenv("RISK_MAX_SINGLE_TRANSFER_CENTS", "40000000"))
DAILY_LIMIT_CENTS = int(os.getenv("RISK_DAILY_LIMIT_CENTS", "80000000"))
