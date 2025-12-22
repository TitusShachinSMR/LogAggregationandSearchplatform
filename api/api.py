from fastapi import FastAPI, Header, HTTPException
import psycopg2
import time

app = FastAPI()

conn = None

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
        print("Postgres not ready for API, waiting...")
        time.sleep(2)

print("API connected to Postgres")


@app.get("/logs")
def get_logs(
    x_tenant_id: str = Header(None),
    level: str = None,
    service: str = None,
    limit: int = 50
):
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header missing")

    cur = conn.cursor()

    query = """
        SELECT service, level, message, timestamp
        FROM logs
        WHERE tenant_id = %s
    """
    params = [x_tenant_id]

    if level:
        query += " AND level = %s"
        params.append(level)

    if service:
        query += " AND service = %s"
        params.append(service)

    query += " ORDER BY timestamp DESC LIMIT %s"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()

    return [
        {
            "service": r[0],
            "level": r[1],
            "message": r[2],
            "timestamp": r[3]
        }
        for r in rows
    ]