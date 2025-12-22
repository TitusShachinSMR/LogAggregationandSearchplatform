import redis
import psycopg2
import time

# -------------------------
# Redis connection
# -------------------------
r = redis.Redis(host="redis", port=6379, decode_responses=True)

# -------------------------
# Wait for Postgres
# -------------------------
while True:
    try:
        conn = psycopg2.connect(
            host="postgres",
            database="logsdb",
            user="logsuser",
            password="logspass"
        )
        break
    except psycopg2.OperationalError:
        print("Postgres not ready, waiting...")
        time.sleep(2)

cursor = conn.cursor()
print("Connected to Postgres")

# -------------------------
# Redis stream offset
# -------------------------
last_id = "0"   # 👈 THIS WAS MISSING

print("Consumer started, waiting for logs...")

while True:
    streams = r.xread(
        {"logs_stream": last_id},
        block=0,
        count=10
    )

    for stream, messages in streams:
        for message_id, data in messages:
            tenant_id = data.get("tenant_id")
            service = data.get("service")
            level = data.get("level")
            message = data.get("message")
            timestamp = data.get("timestamp")

            if not tenant_id:
                print("Skipping log without tenant_id:", data)
                last_id = message_id
                continue

            cursor.execute(
                """
                INSERT INTO logs (tenant_id, service, level, message, timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (tenant_id, service, level, message, timestamp)
            )

            conn.commit()

            print(f"Consumed [{tenant_id}] {level} {service}: {message}")

            # advance stream offset
            last_id = message_id
