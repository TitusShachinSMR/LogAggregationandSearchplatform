import redis
import psycopg2
import time
import os

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

while True:
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            database=os.getenv("POSTGRES_DB", "logsdb"),
            user=os.getenv("POSTGRES_USER", "logsuser"),
            password=os.getenv("POSTGRES_PASSWORD", "logspass")
        )
        break
    except psycopg2.OperationalError:
        print("Postgres not ready, waiting...")
        time.sleep(2)

print("Consumer connected to Postgres, waiting for logs...")

last_id = "0"

while True:
    try:
        streams = r.xread({"logs_stream": last_id}, block=0, count=10)

        for stream, messages in streams:
            with conn.cursor() as cur:
                for message_id, data in messages:
                    tenant_id = data.get("tenant_id")
                    service   = data.get("service", "")
                    level     = data.get("level", "INFO")
                    message   = data.get("message")
                    timestamp = data.get("timestamp")

                    if not tenant_id or not message:
                        last_id = message_id
                        continue

                    if timestamp:
                        cur.execute(
                            "INSERT INTO logs (tenant_id, service, level, message, timestamp) VALUES (%s, %s, %s, %s, %s::timestamptz)",
                            (tenant_id, service, level, message, timestamp)
                        )
                    else:
                        cur.execute(
                            "INSERT INTO logs (tenant_id, service, level, message) VALUES (%s, %s, %s, %s)",
                            (tenant_id, service, level, message)
                        )

                    print(f"[{level}] {tenant_id[:8]}… {service}: {message}")
                    last_id = message_id

            conn.commit()

    except Exception as e:
        print(f"Consumer error: {e}, retrying in 2s...")
        conn.rollback()
        time.sleep(2)
