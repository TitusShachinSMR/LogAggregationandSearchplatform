-- =========================
-- USERS
-- =========================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- ORGANIZATIONS
-- =========================
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- USER ↔ ORGANIZATION (many-to-many)
-- =========================
CREATE TABLE user_organizations (
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    org_id INT REFERENCES organizations(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, org_id)
);

-- =========================
-- PROJECTS (1 project = 1 tenant)
-- =========================
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    org_id INT REFERENCES organizations(id) ON DELETE CASCADE,
    project_name TEXT NOT NULL,
    tenant_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- LOGS (tenant-scoped)
-- =========================
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    service TEXT,
    level TEXT,
    message TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- INDEXES (important)
-- =========================
CREATE INDEX idx_logs_tenant ON logs(tenant_id);
CREATE INDEX idx_logs_level ON logs(level);
CREATE INDEX idx_logs_timestamp ON logs(timestamp);
