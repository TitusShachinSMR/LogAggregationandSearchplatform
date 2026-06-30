# Log Aggregation & Search Platform

A multi-tenant log aggregation, search, and analytics platform. Applications ship logs through a collector pipeline, which queues them in Redis and stores them in PostgreSQL. Users manage projects via a React dashboard with real-time search and charts.

---

## Architecture

```
dummy-app (any app)
    │  stdout JSON
    │  Docker fluentd logging driver
    ▼
Fluent Bit (:24224)          ← log collector
    │  POST /ingest
    ▼
FastAPI (:8000)              ← API — pushes to Redis
    │
    ▼
Redis logs_stream            ← message queue / write buffer
    │
    ▼
Consumer (Python)            ← reads stream, batch inserts
    │
    ▼
PostgreSQL                   ← persistent storage
    ▲
    │  SELECT + analytics queries
    ▼
React Dashboard (:5173)      ← frontend
```

### Why each component exists

| Component | Why |
|---|---|
| **Fluent Bit** | Collects logs from any app without code changes. Apps write to stdout, Fluent Bit ships it. Real-world pattern used by Datadog, Loki, ELK. |
| **Redis Stream** | Write buffer — API returns instantly, consumer handles DB inserts async. Under high load, messages queue instead of blocking. |
| **Consumer** | Decoupled writer — reads from Redis, batch-inserts into Postgres. If Postgres is slow, Redis absorbs the pressure. |
| **FastAPI** | REST API — log ingestion, search, analytics, auth. Read queries go directly to Postgres. |
| **PostgreSQL** | Persistent indexed storage with multi-tenant isolation via `tenant_id`. |
| **React** | Dashboard — project switcher, log search, analytics charts. |

---

## Multi-Tenancy

Every project gets a UUID called `tenant_id`. Every log row is tagged with it. Every read query filters by it.

```sql
-- Every query looks like this
SELECT * FROM logs WHERE tenant_id = 'abc-123' AND level = 'ERROR'
```

The `X-Tenant-ID` header on every API request identifies which project's data to read. Users can have multiple projects — switching tabs in the dashboard switches the active `tenant_id`.

```
User A (tenant: abc-123) → can only see their logs
User B (tenant: xyz-789) → can only see their logs
```

---

## Authentication — JWT

```
POST /auth/signup  →  bcrypt hashes password  →  returns JWT token
POST /auth/login   →  verifies password hash   →  returns JWT token
```

Every protected endpoint requires:
```
Authorization: Bearer <token>
```

FastAPI validates it via `Depends(verify_token)`:
```python
def verify_token(credentials = Depends(bearer_scheme)) -> dict:
    payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    return payload
```

Token contains: `user_id`, `username`, `exp` (expiry). Signed with `HS256`.

Only `/auth/signup`, `/auth/login`, and `/ingest` are public. Everything else requires a valid token.

---

## Log Pipeline — Step by Step

### Path 1: dummy-app via Fluent Bit (automatic, no code change)
1. `dummy-app` prints JSON to stdout every 5 seconds
2. Docker's fluentd logging driver ships stdout to Fluent Bit on port `24224`
3. Fluent Bit parses the JSON field out of Docker's log wrapper
4. Fluent Bit POSTs to `POST /ingest` on the API
5. API calls `r.xadd("logs_stream", {...})` — pushes to Redis Stream
6. Consumer reads with `r.xread({"logs_stream": last_id}, block=0, count=10)`
7. Consumer batch-inserts into Postgres and commits once per batch

### Path 2: Friend's app via API (direct SDK integration)
1. Friend calls `POST /logs` with `X-Tenant-ID` header and `Authorization: Bearer <token>`
2. API pushes to Redis Stream
3. Consumer reads and inserts — same path from step 6 above

### Why Redis Streams (not pub/sub, not a list)?
- **Persistent** — messages survive Redis restarts
- **Offset tracking** — consumer remembers `last_id`, never reprocesses
- **Replay** — can re-read from any point in history
- **Consumer groups** — future: multiple consumers can share load

---

## API Endpoints

### Auth (public)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/signup` | Create account, returns JWT |
| POST | `/auth/login` | Login, returns JWT |

### Projects (JWT required)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects` | Create project, returns `tenant_id` |
| GET | `/users/{user_id}/projects` | List user's projects |
| DELETE | `/projects/{project_id}?user_id=` | Delete project + all its logs |

### Logs (JWT + X-Tenant-ID required)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/logs` | Ingest a log entry (queues to Redis) |
| GET | `/logs` | List recent logs |
| GET | `/logs/search` | Search by keyword, level, service, time range |
| POST | `/ingest` | Internal — Fluent Bit batch ingestion (no auth) |

### Analytics (JWT + X-Tenant-ID required)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/analytics/summary` | Total, error, warning counts |
| GET | `/analytics/by-level` | Count grouped by level |
| GET | `/analytics/by-service` | Count grouped by service |
| GET | `/analytics/logs-per-day` | Count per calendar day |
| GET | `/analytics/day-breakdown?date=YYYY-MM-DD` | Hourly INFO/WARN/ERROR for a specific day |
| GET | `/analytics/error-trend` | ERROR count per hour over time |
| GET | `/analytics/top-error-services` | Services with most errors |

---

## Database Schema

```sql
-- USERS
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    email         VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ORGANIZATIONS
CREATE TABLE organizations (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- USER <-> ORGANIZATION (many-to-many)
CREATE TABLE user_organizations (
    user_id INT,
    org_id  INT,
    PRIMARY KEY (user_id, org_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (org_id)  REFERENCES organizations(id) ON DELETE CASCADE
);

-- PROJECTS (1 project = 1 tenant)
CREATE TABLE projects (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    owner_id     INT,
    project_name VARCHAR(150) NOT NULL,
    tenant_id    VARCHAR(100) UNIQUE NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- LOGS (tenant-scoped)
CREATE TABLE logs (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id VARCHAR(100) NOT NULL,
    service   VARCHAR(100),
    level     VARCHAR(20),
    message   TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES projects(tenant_id) ON DELETE CASCADE
);

-- Indexes for fast queries
CREATE INDEX idx_logs_tenant    ON logs(tenant_id);
CREATE INDEX idx_logs_level     ON logs(level);
CREATE INDEX idx_logs_service   ON logs(service);
CREATE INDEX idx_logs_timestamp ON logs(timestamp);
```

---

## Fluent Bit Config Explained

```ini
[SERVICE]
    Flush 1              # send buffered logs every 1 second

[INPUT]
    Name    forward      # listen for Docker's fluentd logging driver
    Port    24224        # standard Fluentd port

[FILTER]
    Name     parser
    Key_Name log         # Docker wraps stdout in a "log" field
    Parser   json_log    # parse it as JSON → extracts tenant_id, service etc.

[OUTPUT]
    Name   http
    Host   api           # container name — Docker internal DNS
    Port   8000
    URI    /ingest        # POST to this endpoint
    Format json
```

### Why not the Redis output plugin?
Fluent Bit v2.2 has no built-in Redis output plugin. HTTP output to the API is cleaner — the API validates the payload before queuing to Redis.

---

## Docker Compose Services

```
redis      ← message queue, port 6379
postgres   ← database, port 5432, data persisted in pgdata volume
fluent-bit ← log collector, port 24224
dummy-app  ← simulated friend's app, logs via Docker fluentd driver
consumer   ← reads Redis stream, writes to Postgres
api        ← FastAPI backend, port 8000
```

`dummy-app` uses Docker's fluentd logging driver — zero code change needed to ship logs:
```yaml
logging:
  driver: fluentd
  options:
    fluentd-address: "localhost:24224"
```

---

## Running Locally

```bash
# First time or after schema changes
docker compose down -v
docker compose up --build

# Normal restart
docker compose up --build

# Frontend
cd frontend
npm install
npm run dev
```

| Service | URL |
|---|---|
| React Dashboard | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |

---

## Frontend — How It Works

```
/signup  →  POST /auth/signup  →  stores JWT in localStorage  →  /dashboard
/login   →  POST /auth/login   →  stores JWT in localStorage  →  /dashboard
```

Every axios request auto-attaches the JWT:
```js
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})
```

On 401 → clears storage → redirects to `/login` automatically.

Dashboard loads all projects for the user, renders one tab per project. Clicking a tab switches the active `tenant_id` and reloads all charts and logs for that project.

**Charts:**
- Pie — log count by level (INFO/WARN/ERROR)
- Bar — log count by service
- Area — error trend over time (hourly)
- Bar (drillable) — logs per day → click a day → hourly stacked INFO/WARN/ERROR

---

## How a Friend Integrates Their App

### Option A — Docker app (zero code change)
Add to their `docker-compose.yml`:
```yaml
their-service:
  image: their-image
  logging:
    driver: fluentd
    options:
      fluentd-address: "your-platform-host:24224"
      tag: "their-service"
```

### Option B — Direct API call
```python
import requests
requests.post("http://your-platform:8000/logs",
    headers={"X-Tenant-ID": "their-tenant-uuid",
             "Authorization": "Bearer their-jwt-token"},
    json={"service": "auth", "level": "ERROR", "message": "Login failed"})
```

---

## Common Interview Questions

**Q: Why Redis between the API and Postgres?**
> The API returns immediately after pushing to Redis. The consumer handles the Postgres write asynchronously. Under high load (many tenants sending logs), Redis absorbs the burst — messages queue instead of hammering Postgres directly.

**Q: Why Fluent Bit instead of calling the API directly?**
> Real apps can't always be modified. Fluent Bit is a sidecar — it ships logs from any app that writes to stdout, with no code changes. Same pattern used by Datadog agents, Grafana Alloy, Logstash.

**Q: How is tenant data isolated?**
> Every log row has a `tenant_id` column. Every API query has `WHERE tenant_id = %s`. The `X-Tenant-ID` header on requests is validated by JWT (the token proves who you are, the header says which project's data you want).

**Q: What would you improve for production?**
> Connection pooling (`psycopg2.pool`), Redis consumer groups for horizontal scaling of the consumer, token refresh / short-lived access tokens, rate limiting per tenant, log retention policy (delete logs older than N days).

**Q: How does the drill-down chart work?**
> `GET /analytics/logs-per-day` returns total counts per day. Clicking a bar calls `GET /analytics/day-breakdown?date=YYYY-MM-DD` which returns hourly counts split by level (INFO/WARN/ERROR). The frontend switches between the two views without a page reload.

**Q: What is a Redis Stream vs pub/sub?**
> Pub/sub is fire-and-forget — if the consumer is down, messages are lost. A Stream is persistent — messages survive, the consumer tracks its position (`last_id`) and resumes from where it left off after a restart.

---

## Interview Reference — Express.js Equivalent

> This project uses FastAPI + PostgreSQL. For interviews, the equivalent in Express.js + MySQL is shown below — simpler syntax, more universally recognized.

### FastAPI vs Express — Key Differences

| Thing | FastAPI (Python) | Express (Node.js) |
|---|---|---|
| Route decorator | `@app.get("/path")` | `app.get("/path", handler)` |
| Auth middleware | `Depends(verify_token)` | `verifyToken` as middle argument |
| Request body | Pydantic model auto-parsed | `req.body` (needs `express.json()`) |
| Query params | Function params with defaults | `req.query.param` |
| Path params | `{user_id}` in path | `:user_id` → `req.params.user_id` |
| Headers | `Header(..., alias="X-Tenant-ID")` | `req.headers["x-tenant-id"]` |
| DB placeholders | `%s` (psycopg2 / PostgreSQL) | `?` (mysql2) |
| Error response | `raise HTTPException(404, ...)` | `return res.status(404).json(...)` |
| Async | `async def` + `await` | `async (req, res) =>` + `await` |

### PostgreSQL vs MySQL — Query Differences

| Feature | PostgreSQL | MySQL |
|---|---|---|
| Placeholders | `$1, $2, $3` | `?, ?, ?` |
| Get inserted ID | `RETURNING id` | `result.insertId` |
| Case-insensitive search | `ILIKE '%keyword%'` | `LIKE '%keyword%'` (case-insensitive by default) |
| Conditional count | `COUNT(*) FILTER (WHERE level='ERROR')` | `SUM(level = 'ERROR')` |
| Truncate to hour | `DATE_TRUNC('hour', timestamp)` | `DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00')` |
| Auto-increment | `SERIAL` | `INT AUTO_INCREMENT` |

### Express.js + MySQL Implementation

```js
const express = require("express");
const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");
const mysql = require("mysql2/promise");
const { v4: uuidv4 } = require("uuid");

const app = express();
app.use(express.json());

const JWT_SECRET = process.env.JWT_SECRET || "dev-secret";

// -------------------------
// DB Connection
// -------------------------
const pool = mysql.createPool({
  host:     process.env.MYSQL_HOST     || "localhost",
  database: process.env.MYSQL_DB       || "logsdb",
  user:     process.env.MYSQL_USER     || "logsuser",
  password: process.env.MYSQL_PASSWORD || "logspass",
});

// -------------------------
// Auth Middleware
// -------------------------
function verifyToken(req, res, next) {
  const authHeader = req.headers["authorization"];
  if (!authHeader) return res.status(401).json({ detail: "No token" });

  const token = authHeader.split(" ")[1]; // "Bearer <token>"
  try {
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch (err) {
    return res.status(401).json({ detail: "Invalid or expired token" });
  }
}

// ===========================
// Auth
// ===========================

// POST /auth/signup
app.post("/auth/signup", async (req, res) => {
  const { username, email, password } = req.body;
  const password_hash = await bcrypt.hash(password, 10);
  try {
    const [result] = await pool.query(
      "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
      [username, email, password_hash]
    );
    const user_id = result.insertId;
    const token = jwt.sign({ sub: user_id, username }, JWT_SECRET, { expiresIn: "24h" });
    res.status(201).json({ user_id, username, token });
  } catch (err) {
    res.status(400).json({ detail: "Username or email already exists" });
  }
});

// POST /auth/login
app.post("/auth/login", async (req, res) => {
  const { username, password } = req.body;
  const [rows] = await pool.query(
    "SELECT id, password_hash FROM users WHERE username = ?",
    [username]
  );
  const user = rows[0];
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ detail: "Invalid username or password" });
  }
  const token = jwt.sign({ sub: user.id, username }, JWT_SECRET, { expiresIn: "24h" });
  res.json({ user_id: user.id, username, token });
});

// ===========================
// Projects
// ===========================

// POST /projects
app.post("/projects", verifyToken, async (req, res) => {
  const { name, user_id } = req.body;
  const tenant_id = uuidv4();
  const [userCheck] = await pool.query("SELECT id FROM users WHERE id = ?", [user_id]);
  if (!userCheck[0]) return res.status(404).json({ detail: "User not found" });
  const [result] = await pool.query(
    "INSERT INTO projects (project_name, tenant_id, owner_id) VALUES (?, ?, ?)",
    [name, tenant_id, user_id]
  );
  res.status(201).json({ project_id: result.insertId, project_name: name, tenant_id });
});

// GET /users/:user_id/projects
app.get("/users/:user_id/projects", verifyToken, async (req, res) => {
  const { user_id } = req.params;
  const [rows] = await pool.query(
    "SELECT id, project_name, tenant_id, created_at FROM projects WHERE owner_id = ? ORDER BY created_at DESC",
    [user_id]
  );
  res.json(rows);
});

// DELETE /projects/:project_id
app.delete("/projects/:project_id", verifyToken, async (req, res) => {
  const { project_id } = req.params;
  const { user_id } = req.query;
  const [rows] = await pool.query(
    "SELECT tenant_id, owner_id FROM projects WHERE id = ?", [project_id]
  );
  const project = rows[0];
  if (!project) return res.status(404).json({ detail: "Project not found" });
  if (project.owner_id != user_id) return res.status(403).json({ detail: "Not your project" });
  await pool.query("DELETE FROM logs WHERE tenant_id = ?", [project.tenant_id]);
  await pool.query("DELETE FROM projects WHERE id = ?", [project_id]);
  res.json({ deleted: true, project_id });
});

// ===========================
// Logs
// ===========================

// POST /logs
app.post("/logs", verifyToken, async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"];
  const { service, level, message } = req.body;
  const timestamp = new Date().toISOString().slice(0, 19).replace("T", " ");
  await pool.query(
    "INSERT INTO logs (tenant_id, service, level, message, timestamp) VALUES (?, ?, ?, ?, ?)",
    [tenant_id, service, level, message, timestamp]
  );
  res.status(201).json({ queued: true, tenant_id, service, level, message, timestamp });
});

// GET /logs
app.get("/logs", verifyToken, async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"];
  const { level, service, limit = 50 } = req.query;
  let query = "SELECT service, level, message, timestamp FROM logs WHERE tenant_id = ?";
  const params = [tenant_id];
  if (level)   { params.push(level);   query += " AND level = ?"; }
  if (service) { params.push(service); query += " AND service = ?"; }
  params.push(Number(limit)); query += " ORDER BY timestamp DESC LIMIT ?";
  const [rows] = await pool.query(query, params);
  res.json(rows);
});

// GET /logs/search
app.get("/logs/search", verifyToken, async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"];
  const { keyword, level, service, start_time, end_time, limit = 100 } = req.query;
  let query = "SELECT service, level, message, timestamp FROM logs WHERE tenant_id = ?";
  const params = [tenant_id];
  if (keyword)    { params.push(`%${keyword}%`); query += " AND message LIKE ?"; }
  if (level)      { params.push(level);          query += " AND level = ?"; }
  if (service)    { params.push(service);        query += " AND service = ?"; }
  if (start_time) { params.push(start_time);     query += " AND timestamp >= ?"; }
  if (end_time)   { params.push(end_time);       query += " AND timestamp <= ?"; }
  params.push(Number(limit)); query += " ORDER BY timestamp DESC LIMIT ?";
  const [rows] = await pool.query(query, params);
  res.json(rows);
});

// ===========================
// Analytics
// ===========================

// GET /analytics/summary
app.get("/analytics/summary", verifyToken, async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"];
  const [rows] = await pool.query(
    `SELECT
       COUNT(*)                      AS total_logs,
       SUM(level = 'ERROR')          AS error_logs,
       SUM(level = 'WARN')           AS warning_logs
     FROM logs WHERE tenant_id = ?`,
    [tenant_id]
  );
  res.json(rows[0]);
});

// GET /analytics/by-service
app.get("/analytics/by-service", verifyToken, async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"];
  const [rows] = await pool.query(
    "SELECT service, COUNT(*) AS count FROM logs WHERE tenant_id = ? GROUP BY service ORDER BY count DESC",
    [tenant_id]
  );
  res.json(rows);
});

// GET /analytics/by-level
app.get("/analytics/by-level", verifyToken, async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"];
  const [rows] = await pool.query(
    "SELECT level, COUNT(*) AS count FROM logs WHERE tenant_id = ? GROUP BY level",
    [tenant_id]
  );
  res.json(rows);
});

// GET /analytics/logs-per-day
app.get("/analytics/logs-per-day", verifyToken, async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"];
  const [rows] = await pool.query(
    "SELECT DATE(timestamp) AS day, COUNT(*) AS count FROM logs WHERE tenant_id = ? GROUP BY day ORDER BY day",
    [tenant_id]
  );
  res.json(rows);
});

// GET /analytics/error-trend
app.get("/analytics/error-trend", verifyToken, async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"];
  const [rows] = await pool.query(
    `SELECT DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') AS hour, COUNT(*) AS count
     FROM logs WHERE tenant_id = ? AND level = 'ERROR'
     GROUP BY hour ORDER BY hour`,
    [tenant_id]
  );
  res.json(rows);
});

app.listen(3000, () => console.log("API running on port 3000"));
```

---

## What You'd Do Differently at Scale

| Current | Production |
|---|---|
| Single psycopg2 connection | Connection pool |
| JWT stored in localStorage | HttpOnly cookie |
| One consumer instance | Consumer groups (Redis XREADGROUP) |
| No rate limiting | Per-tenant rate limits |
| Logs kept forever | Retention policy (TTL or cron delete) |
| bcrypt on every login | Same — bcrypt is correct for passwords |
