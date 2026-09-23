-- Future Postgres / Supabase RLS. Not applied on SQLite.
-- Server authorization in FastAPI is the security boundary for local/dev.

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE design_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- Authenticated JWT claims: request.jwt.claims->>'sub' and request.jwt.claims->>'role'
-- Clients and architects see only assigned projects; admin/IT see all.

CREATE POLICY projects_select ON projects
    FOR SELECT
    USING (
        current_setting('request.jwt.claims', true)::json->>'role' IN ('MAIN_ADMIN', 'IT_PERSONNEL')
        OR client_id = current_setting('request.jwt.claims', true)::json->>'sub'
        OR architect_id = current_setting('request.jwt.claims', true)::json->>'sub'
    );

CREATE POLICY revisions_update_architect ON revisions
    FOR UPDATE
    USING (
        current_setting('request.jwt.claims', true)::json->>'role' = 'ARCHITECT'
        AND source_type <> 'PUBLISHED'
        AND EXISTS (
            SELECT 1 FROM design_documents d
            JOIN projects p ON p.id = d.project_id
            WHERE d.id = revisions.design_document_id
              AND p.architect_id = current_setting('request.jwt.claims', true)::json->>'sub'
              AND p.status <> 'PUBLISHED'
        )
    );

CREATE POLICY notifications_own ON notifications
    FOR SELECT
    USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');
