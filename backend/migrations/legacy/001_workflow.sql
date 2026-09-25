-- KIYUB workflow schema (SQLite + Postgres compatible).
-- Apply on Postgres/Supabase later; SQLite uses SQLAlchemy create_all at startup.

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL,
    approved BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    client_id VARCHAR(36) REFERENCES users(id),
    architect_id VARCHAR(36) REFERENCES users(id),
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS client_briefs (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL UNIQUE REFERENCES projects(id),
    questionnaire TEXT NOT NULL DEFAULT '{}',
    specification TEXT NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS design_documents (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id),
    stage VARCHAR(32) NOT NULL DEFAULT 'CLIENT_BRIEF',
    current_revision_id VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS revisions (
    id VARCHAR(36) PRIMARY KEY,
    design_document_id VARCHAR(36) NOT NULL REFERENCES design_documents(id),
    version INTEGER NOT NULL,
    source_revision_id VARCHAR(36) REFERENCES revisions(id),
    scene_document TEXT NOT NULL DEFAULT '{}',
    floor_plan TEXT NOT NULL DEFAULT '{}',
    created_by VARCHAR(36) NOT NULL REFERENCES users(id),
    source_type VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id),
    requested_by VARCHAR(36) NOT NULL REFERENCES users(id),
    source_revision_id VARCHAR(36),
    source_brief_id VARCHAR(36),
    specification TEXT NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    result_candidate_id VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_candidates (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id),
    generation_job_id VARCHAR(36) REFERENCES generation_jobs(id),
    revision_id VARCHAR(36) NOT NULL REFERENCES revisions(id),
    selected_by_client BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comments (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id),
    stage VARCHAR(32),
    revision_id VARCHAR(36) REFERENCES revisions(id),
    author_id VARCHAR(36) NOT NULL REFERENCES users(id),
    object_id VARCHAR(64),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS approvals (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id),
    revision_id VARCHAR(36) REFERENCES revisions(id),
    actor_id VARCHAR(36) NOT NULL REFERENCES users(id),
    kind VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(36) PRIMARY KEY,
    actor_id VARCHAR(36) REFERENCES users(id),
    project_id VARCHAR(36) REFERENCES projects(id),
    revision_id VARCHAR(36),
    event_type VARCHAR(64) NOT NULL,
    target VARCHAR(128),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    project_id VARCHAR(36) REFERENCES projects(id),
    kind VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invitations (
    id VARCHAR(36) PRIMARY KEY,
    architect_id VARCHAR(36) NOT NULL REFERENCES users(id),
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id),
    email VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMPTZ,
    accepted_user_id VARCHAR(36) REFERENCES users(id)
);
