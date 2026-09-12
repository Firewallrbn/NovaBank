import os

SERVICE_NAME = "orchestrator"
DB_PATH = os.getenv("DB_PATH", "/data/orchestrator.db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

ACCOUNT_URL = os.getenv("ACCOUNT_URL", "http://account-service:8000")
RISK_URL = os.getenv("RISK_URL", "http://risk-service:8000")
CLEARING_URL = os.getenv("CLEARING_URL", "http://clearing-service:8000")

HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
RECOVERY_INTERVAL_SECONDS = float(os.getenv("RECOVERY_INTERVAL_SECONDS", "15"))
