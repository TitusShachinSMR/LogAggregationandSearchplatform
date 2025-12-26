from fastapi import FastAPI, Header, HTTPException
import psycopg2
import time
import uuid
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    level: str|None = None,
    service: str|None = None,
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
    
@app.get("/logs/search")
def search_logs(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    level: str | None = None,
    service: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100
):
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

    if start_time:
        query += " AND timestamp >= %s"
        params.append(start_time)

    if end_time:
        query += " AND timestamp <= %s"
        params.append(end_time)

    query += " ORDER BY timestamp DESC LIMIT %s"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [
        {"service": r[0], "level": r[1], "message": r[2], "timestamp": r[3]}
        for r in rows
    ]
@app.get("/analytics/by-service")
def logs_by_service(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT service, COUNT(*)
            FROM logs
            WHERE tenant_id = %s
            GROUP BY service
            ORDER BY COUNT(*) DESC
        """, (x_tenant_id,))
        rows = cur.fetchall()

    return [{"service": r[0], "count": r[1]} for r in rows]

@app.get("/analytics/by-level")
def logs_by_level(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT level, COUNT(*)
            FROM logs
            WHERE tenant_id = %s
            GROUP BY level
        """, (x_tenant_id,))
        rows = cur.fetchall()

    return [{"level": r[0], "count": r[1]} for r in rows]

@app.get("/analytics/logs-per-day")
def logs_per_day(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DATE(timestamp) AS day, COUNT(*)
            FROM logs
            WHERE tenant_id = %s
            GROUP BY day
            ORDER BY day
        """, (x_tenant_id,))
        rows = cur.fetchall()

    return [{"day": str(r[0]), "count": r[1]} for r in rows]
@app.get("/analytics/logs-per-hour")
def logs_per_hour(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXTRACT(HOUR FROM timestamp) AS hour, COUNT(*)
            FROM logs
            WHERE tenant_id = %s
            GROUP BY hour
            ORDER BY hour
        """, (x_tenant_id,))
        rows = cur.fetchall()

    return [{"hour": int(r[0]), "count": r[1]} for r in rows]
@app.get("/analytics/error-trend")
def error_trend(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DATE_TRUNC('hour', timestamp) AS hour, COUNT(*)
            FROM logs
            WHERE tenant_id = %s AND level = 'ERROR'
            GROUP BY hour
            ORDER BY hour
        """, (x_tenant_id,))
        rows = cur.fetchall()

    return [{"hour": str(r[0]), "count": r[1]} for r in rows]
@app.get("/analytics/top-error-services")
def top_error_services(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    limit: int = 5
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT service, COUNT(*)
            FROM logs
            WHERE tenant_id = %s AND level = 'ERROR'
            GROUP BY service
            ORDER BY COUNT(*) DESC
            LIMIT %s
        """, (x_tenant_id, limit))
        rows = cur.fetchall()

    return [{"service": r[0], "error_count": r[1]} for r in rows]
@app.get("/analytics/summary")
def summary(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE level='ERROR') AS errors,
              COUNT(*) FILTER (WHERE level='WARN') AS warnings
            FROM logs
            WHERE tenant_id = %s
        """, (x_tenant_id,))
        row = cur.fetchone()

    return {
        "total_logs": row[0],
        "error_logs": row[1],
        "warning_logs": row[2]
    }    
# -------------------------
# Models
# -------------------------
class UserCreate(BaseModel):
    username: str
    email: str


class ProjectCreate(BaseModel):
    name: str
    user_id: int


# -------------------------
# Create user
# -------------------------
@app.post("/users")
def create_user(user: UserCreate):
    with conn.cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO users (username, email) VALUES (%s, %s) RETURNING id",
                (user.username, user.email)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Username already exists")

    return {
        "user_id": user_id,
        "username": user.username
    }


# -------------------------
# Create project for user
# -------------------------
@app.post("/projects")
def create_project(project: ProjectCreate):
    tenant_id = str(uuid.uuid4())

    with conn.cursor() as cur:
        # Check user exists
        cur.execute(
            "SELECT id FROM users WHERE id = %s",
            (project.user_id,)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        # Insert project
        cur.execute(
            """
            INSERT INTO projects (project_name, tenant_id, owner_id)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (project.name, tenant_id, project.user_id)
        )
        project_id = cur.fetchone()[0]
        conn.commit()

    return {
        "project_id": project_id,
        "project_name": project.name,
        "tenant_id": tenant_id
    }


# -------------------------
# Get projects for user
# -------------------------
@app.get("/users/{user_id}/projects")
def get_projects_for_user(user_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, project_name, tenant_id
            FROM projects
            WHERE owner_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        rows = cur.fetchall()

    if not rows:
        return []

    return [
        {
            "project_id": r[0],
            "project_name": r[1],
            "tenant_id": r[2]
        }
        for r in rows
    ]
