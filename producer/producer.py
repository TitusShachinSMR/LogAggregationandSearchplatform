import redis
import json
import time
import random
from datetime import datetime

r = redis.Redis(host="redis", port=6379, decode_responses=True)

TENANTS = [
    "tenant_project_auth",
    "tenant_project_payments",
    "6720833e-6eaf-4b5d-b0a4-28c6ea99142b"
]

SERVICES = ["auth-service", "payment-service", "user-service"]
LEVELS = ["INFO", "ERROR", "WARN"]

while True:
    log = {
        "tenant_id": random.choice(TENANTS),
        "service": random.choice(SERVICES),
        "level": random.choice(LEVELS),
        "message": "Sample log message",
        "timestamp": datetime.utcnow().isoformat()
    }

    r.xadd("logs_stream", log)
    print("Produced:", log)

    time.sleep(3)
