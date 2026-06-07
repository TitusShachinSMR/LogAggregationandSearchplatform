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
users (id, username, email, password_hash, created_at)
projects (id, owner_id → users, project_name, tenant_id UUID, created_at)
logs (id, tenant_id, service, level, message, timestamp)
organizations, user_organizations  ← for future org-level grouping

-- Indexes for fast queries
idx_logs_tenant    ON logs(tenant_id)
idx_logs_level     ON logs(level)
idx_logs_service   ON logs(service)
idx_logs_timestamp ON logs(timestamp)
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

## What You'd Do Differently at Scale

| Current | Production |
|---|---|
| Single psycopg2 connection | Connection pool |
| JWT stored in localStorage | HttpOnly cookie |
| One consumer instance | Consumer groups (Redis XREADGROUP) |
| No rate limiting | Per-tenant rate limits |
| Logs kept forever | Retention policy (TTL or cron delete) |
| bcrypt on every login | Same — bcrypt is correct for passwords |
