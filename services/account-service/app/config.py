import os

SERVICE_NAME = "account-service"
QUEUE_NAME = "account-service.events"
DB_PATH = os.getenv("DB_PATH", "/data/account.db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
