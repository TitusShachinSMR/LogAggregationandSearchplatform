import logging
import time
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

services = ["auth-service", "payment-service", "user-service"]

while True:
    service = random.choice(services)
    level = random.choice(["INFO", "ERROR", "WARNING"])

    if level == "ERROR":
        logging.error(f"{service} failed to process request")
    elif level == "WARNING":
        logging.warning(f"{service} slow response detected")
    else:
        logging.info(f"{service} request processed")

    time.sleep(1)
