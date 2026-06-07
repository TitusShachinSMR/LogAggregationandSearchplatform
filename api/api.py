from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import bcrypt
import time
import uuid
import os
from pydantic import BaseModel, Field

app = FastAPI(
    title="Log Aggregation & Search Platform",
    description=(
        "Multi-tenant log ingestion, search, and analytics API.\n\n"
        "**Quick start:**\n"
        "1. `POST /auth/signup` — create account\n"
        "2. `POST /auth/login` — get user_id back\n"
        "3. `POST /projects` — create a project, get tenant_id\n"
        "4. `POST /logs` — ship logs with X-Tenant-ID header\n"
        "5. `GET /logs/search` — search your logs"
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = dict(
    host=os.getenv("POSTGRES_HOST", "postgres"),
    database=os.getenv("POSTGRES_DB", "logsdb"),
    user=os.getenv("POSTGRES_USER", "logsuser"),
    password=os.getenv("POSTGRES_PASSWORD", "logspass"),
)

conn = None

while True:
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        break
    except psycopg2.OperationalError:
        print("Postgres not ready, waiting...")
        time.sleep(2)

print("API connected to Postgres")


def get_conn():
    global conn
    try:
        # ping — raises if connection is dead
        conn.isolation_level
    except Exception:
        conn = psycopg2.connect(**DB_CONFIG)
    return conn


# -------------------------
# Models
# -------------------------
class SignupRequest(BaseModel):
    username: str = Field(..., examples=["alice"])
    email: str    = Field(..., examples=["alice@example.com"])
    password: str = Field(..., examples=["secret123"])

class LoginRequest(BaseModel):
    username: str = Field(..., examples=["alice"])
    password: str = Field(..., examples=["secret123"])

class ProjectCreate(BaseModel):
    name: str     = Field(..., examples=["auth-service"])
    user_id: int  = Field(..., examples=[1])

class LogCreate(BaseModel):
    service: str  = Field(..., examples=["auth-service"])
    level: str    = Field(..., examples=["ERROR"], description="INFO | WARN | ERROR")
    message: str  = Field(..., examples=["Login failed for user john"])


# ===========================
# Auth
# ===========================

@app.post("/auth/signup", tags=["Auth"], summary="Create account", status_code=201)
def signup(body: SignupRequest):
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    c = get_conn()
    with c.cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (body.username, body.email, password_hash)
            )
            user_id = cur.fetchone()[0]
            c.commit()
        except psycopg2.errors.UniqueViolation:
            c.rollback()
            raise HTTPException(status_code=400, detail="Username or email already exists")

    return {"user_id": user_id, "username": body.username}


@app.post("/auth/login", tags=["Auth"], summary="Login with username + password")
def login(body: LoginRequest):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute(
            "SELECT id, password_hash FROM users WHERE username = %s",
            (body.username,)
        )
        row = cur.fetchone()

    if not row or not bcrypt.checkpw(body.password.encode(), row[1].encode()):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return {"user_id": row[0], "username": body.username}


# ===========================
# Projects
# ===========================

@app.post("/projects", tags=["Projects"], summary="Create a project — returns tenant_id", status_code=201)
def create_project(project: ProjectCreate):
    tenant_id = str(uuid.uuid4())
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id = %s", (project.user_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        cur.execute(
            "INSERT INTO projects (project_name, tenant_id, owner_id) VALUES (%s, %s, %s) RETURNING id",
            (project.name, tenant_id, project.user_id)
        )
        project_id = cur.fetchone()[0]
        c.commit()

    return {"project_id": project_id, "project_name": project.name, "tenant_id": tenant_id}


@app.get("/users/{user_id}/projects", tags=["Projects"], summary="List all projects for a user")
def get_projects(user_id: int):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute(
            "SELECT id, project_name, tenant_id, created_at FROM projects WHERE owner_id = %s ORDER BY created_at DESC",
            (user_id,)
        )
        rows = cur.fetchall()

    return [
        {"project_id": r[0], "project_name": r[1], "tenant_id": r[2], "created_at": str(r[3])}
        for r in rows
    ]


@app.delete("/projects/{project_id}", tags=["Projects"], summary="Delete a project and all its logs")
def delete_project(project_id: int, user_id: int):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("SELECT tenant_id, owner_id FROM projects WHERE id = %s", (project_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        if row[1] != user_id:
            raise HTTPException(status_code=403, detail="Not your project")

        tenant_id = row[0]
        cur.execute("DELETE FROM logs WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
        c.commit()

    return {"deleted": True, "project_id": project_id}


# ===========================
# Fluent Bit ingestion
# ===========================

@app.post("/ingest", tags=["Logs"], summary="Internal — receives log batches from Fluent Bit")
async def ingest_from_fluentbit(request: Request):
    body = await request.json()
    records = body if isinstance(body, list) else [body]

    inserted = 0
    c = get_conn()
    with c.cursor() as cur:
        for record in records:
            tenant_id = record.get("tenant_id")
            service   = record.get("service")
            level     = record.get("level")
            message   = record.get("message")
            timestamp = record.get("timestamp")

            if not tenant_id or not message:
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
            inserted += 1
        c.commit()

    print(f"[/ingest] inserted {inserted} log(s)")
    return {"inserted": inserted}


# ===========================
# Log Ingestion & Search
# ===========================

@app.post("/logs", tags=["Logs"], summary="Ingest a single log entry", status_code=201)
def ingest_log(
    log: LogCreate,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"]),
):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute(
            "INSERT INTO logs (tenant_id, service, level, message) VALUES (%s, %s, %s, %s) RETURNING id, timestamp",
            (x_tenant_id, log.service, log.level, log.message)
        )
        row = cur.fetchone()
        c.commit()

    return {"id": row[0], "tenant_id": x_tenant_id, "service": log.service,
            "level": log.level, "message": log.message, "timestamp": row[1]}


@app.get("/logs", tags=["Logs"], summary="List recent logs")
def get_logs(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"]),
    level: str | None = None,
    service: str | None = None,
    limit: int = 50,
):
    query = "SELECT service, level, message, timestamp FROM logs WHERE tenant_id = %s"
    params = [x_tenant_id]
    if level:
        query += " AND level = %s"; params.append(level)
    if service:
        query += " AND service = %s"; params.append(service)
    query += " ORDER BY timestamp DESC LIMIT %s"; params.append(limit)

    c = get_conn()
    with c.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [{"service": r[0], "level": r[1], "message": r[2], "timestamp": r[3]} for r in rows]


@app.get("/logs/search", tags=["Logs"], summary="Search logs by keyword, level, service, time range")
def search_logs(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"]),
    keyword: str | None = None,
    level: str | None = None,
    service: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
):
    query = "SELECT service, level, message, timestamp FROM logs WHERE tenant_id = %s"
    params = [x_tenant_id]
    if keyword:
        query += " AND message ILIKE %s"; params.append(f"%{keyword}%")
    if level:
        query += " AND level = %s"; params.append(level)
    if service:
        query += " AND service = %s"; params.append(service)
    if start_time:
        query += " AND timestamp >= %s"; params.append(start_time)
    if end_time:
        query += " AND timestamp <= %s"; params.append(end_time)
    query += " ORDER BY timestamp DESC LIMIT %s"; params.append(limit)

    c = get_conn()
    with c.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [{"service": r[0], "level": r[1], "message": r[2], "timestamp": r[3]} for r in rows]


# ===========================
# Analytics
# ===========================

@app.get("/analytics/summary", tags=["Analytics"], summary="Total, error, and warning counts")
def summary(x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"])):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE level='ERROR'), COUNT(*) FILTER (WHERE level='WARN')
            FROM logs WHERE tenant_id = %s
        """, (x_tenant_id,))
        row = cur.fetchone()
    return {"total_logs": row[0], "error_logs": row[1], "warning_logs": row[2]}


@app.get("/analytics/by-service", tags=["Analytics"], summary="Log count grouped by service")
def logs_by_service(x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"])):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("""
            SELECT service, COUNT(*) FROM logs WHERE tenant_id = %s GROUP BY service ORDER BY COUNT(*) DESC
        """, (x_tenant_id,))
        rows = cur.fetchall()
    return [{"service": r[0], "count": r[1]} for r in rows]


@app.get("/analytics/by-level", tags=["Analytics"], summary="Log count grouped by level")
def logs_by_level(x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"])):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("SELECT level, COUNT(*) FROM logs WHERE tenant_id = %s GROUP BY level", (x_tenant_id,))
        rows = cur.fetchall()
    return [{"level": r[0], "count": r[1]} for r in rows]


@app.get("/analytics/logs-per-day", tags=["Analytics"], summary="Log count per calendar day")
def logs_per_day(x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"])):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("""
            SELECT DATE(timestamp) AS day, COUNT(*) FROM logs WHERE tenant_id = %s GROUP BY day ORDER BY day
        """, (x_tenant_id,))
        rows = cur.fetchall()
    return [{"day": r[0].isoformat(), "count": r[1]} for r in rows]


@app.get("/analytics/day-breakdown", tags=["Analytics"], summary="Hourly INFO/WARN/ERROR counts for a specific day")
def day_breakdown(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"]),
    date: str = None,
):
    if not date:
        raise HTTPException(status_code=400, detail="date query param required (YYYY-MM-DD)")
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("""
            SELECT
                EXTRACT(HOUR FROM timestamp)::int AS hour,
                level,
                COUNT(*) AS count
            FROM logs
            WHERE tenant_id = %s
              AND DATE(timestamp) = %s
            GROUP BY hour, level
            ORDER BY hour
        """, (x_tenant_id, date))
        rows = cur.fetchall()

    # Build hour buckets 0-23 with INFO/WARN/ERROR counts
    buckets = {h: {"hour": h, "INFO": 0, "WARN": 0, "ERROR": 0} for h in range(24)}
    for hour, level, count in rows:
        if level in buckets[hour]:
            buckets[hour][level] = count

    # Only return hours that had any activity
    return [b for b in buckets.values() if b["INFO"] + b["WARN"] + b["ERROR"] > 0]


@app.get("/analytics/error-trend", tags=["Analytics"], summary="ERROR count per hour over time")
def error_trend(x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"])):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("""
            SELECT DATE_TRUNC('hour', timestamp) AS hour, COUNT(*)
            FROM logs WHERE tenant_id = %s AND level = 'ERROR' AND timestamp IS NOT NULL
            GROUP BY hour ORDER BY hour
        """, (x_tenant_id,))
        rows = cur.fetchall()
    return [{"hour": r[0].isoformat(), "count": r[1]} for r in rows if r[0] is not None]


@app.get("/analytics/top-error-services", tags=["Analytics"], summary="Services with most ERROR logs")
def top_error_services(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID", examples=["your-tenant-uuid"]),
    limit: int = 5,
):
    c = get_conn()
    with c.cursor() as cur:
        cur.execute("""
            SELECT service, COUNT(*) FROM logs
            WHERE tenant_id = %s AND level = 'ERROR'
            GROUP BY service ORDER BY COUNT(*) DESC LIMIT %s
        """, (x_tenant_id, limit))
        rows = cur.fetchall()
    return [{"service": r[0], "error_count": r[1]} for r in rows]
