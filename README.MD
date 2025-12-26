import uuid
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# -------------------------

# Database connection

# -------------------------

conn = psycopg2.connect(
host="postgres",
database="logsdb",
user="logsuser",
password="logspass"
)

# -------------------------

# Models

# -------------------------

class UserCreate(BaseModel):
username: str

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
"INSERT INTO users (username) VALUES (%s) RETURNING id",
(user.username,)
)
user_id = cur.fetchone()[0]
conn.commit()
except psycopg2.errors.UniqueViolation:
conn.rollback()
raise HTTPException(status_code=400, detail="Username already exists")

    return {"user_id": user_id, "username": user.username}

# -------------------------

# Create project for user

# -------------------------

@app.post("/projects")
def create_project(project: ProjectCreate):
tenant_id = str(uuid.uuid4())

    with conn.cursor() as cur:
        # Check user exists
        cur.execute("SELECT id FROM users WHERE id = %s", (project.user_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        # Insert project
        cur.execute(
            """
            INSERT INTO projects (name, tenant_id, owner_id)
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

cl
{
"user_id": 1,
"username": "titus"
}
curl -X POST http://localhost:8000/projects \
 -H "Content-Type: application/json" \
 -d '{"name": "auth-service", "user_id": 1}'
{
"project_id": 1,
"project_name": "auth-service",
"tenant_id": "a91f23bc-8d12-4f9b-81f3-0e6cddc98d11"
}
from fastapi import FastAPI, HTTPException
import psycopg2

app = FastAPI()

conn = psycopg2.connect(
host="postgres",
database="logsdb",
user="logsuser",
password="logspass"
)

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
