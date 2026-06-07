import time
import random
import json
from datetime import datetime, timezone

SERVICES = ["auth-service", "payment-service", "user-service"]

MESSAGES = {
    "INFO":  ["User logged in", "Request processed", "Cache hit", "Session started"],
    "WARN":  ["Slow response detected", "Retry attempt", "High memory usage"],
    "ERROR": ["Login failed", "Database timeout", "Payment declined", "Unhandled exception"],
}

# This tenant_id is what you get after registering on the log platform
TENANT_ID = "f436af93-73cd-4ced-8439-169b2be7e2b7"

while True:
    service = random.choice(SERVICES)
    level   = random.choice(list(MESSAGES.keys()))
    message = random.choice(MESSAGES[level])

    # Log as JSON to stdout — Fluent Bit will pick this up via Docker
    print(json.dumps({
        "tenant_id": TENANT_ID,
        "service":   service,
        "level":     level,
        "message":   message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), flush=True)

    time.sleep(5)
