import os

SERVICE_NAME = "api-gateway"
TELEMETRY_QUEUE = "api-gateway.telemetry"
PROJECTION_QUEUE = "api-gateway.projection"

DB_PATH = os.getenv("DB_PATH", "/data/gateway.db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000")
ACCOUNT_URL = os.getenv("ACCOUNT_URL", "http://account-service:8000")
RISK_URL = os.getenv("RISK_URL", "http://risk-service:8000")
CLEARING_URL = os.getenv("CLEARING_URL", "http://clearing-service:8000")
PREFECT_API_URL = os.getenv("PREFECT_API_URL", "http://prefect:4200/api")

PREFECT_UI_URL = os.getenv("PREFECT_UI_URL", "http://localhost:4200")
RABBITMQ_UI_URL = os.getenv("RABBITMQ_UI_URL", "http://localhost:15672")

DISPATCH_RETRY_SECONDS = float(os.getenv("DISPATCH_RETRY_SECONDS", "5"))
