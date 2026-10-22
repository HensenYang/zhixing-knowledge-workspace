BEGIN;
-- Jobs inherited from a single-user deployment have no trustworthy workspace owner.
-- Leave those rows invisible instead of assigning private results to an arbitrary user.
ALTER TABLE knowledge.background_jobs ADD COLUMN workspace_id uuid
    REFERENCES knowledge.workspaces(id) ON DELETE CASCADE
    DEFAULT NULLIF(current_setting('app.workspace_id',true),'')::uuid;
ALTER TABLE knowledge.background_jobs ADD COLUMN created_by uuid
    REFERENCES knowledge.users(id) ON DELETE SET NULL
    DEFAULT NULLIF(current_setting('app.user_id',true),'')::uuid;
UPDATE knowledge.background_jobs SET status='failed', result=NULL,
    error='Legacy task has no workspace owner.', finished_at=now()
    WHERE workspace_id IS NULL AND status IN ('queued','running');
ALTER TABLE knowledge.background_jobs ADD CONSTRAINT background_jobs_workspace_required
    CHECK (workspace_id IS NOT NULL) NOT VALID;
CREATE INDEX background_jobs_workspace_recent_idx ON knowledge.background_jobs(workspace_id,kind,created_at DESC);
CREATE INDEX objects_workspace_active_idx ON knowledge.objects(workspace_id,updated_at DESC,id) WHERE deleted_at IS NULL;
CREATE INDEX relations_workspace_active_idx ON knowledge.relations(workspace_id,created_at DESC,id) WHERE deleted_at IS NULL;
CREATE INDEX canvases_workspace_active_idx ON knowledge.canvases(workspace_id,updated_at DESC,id) WHERE deleted_at IS NULL;
CREATE INDEX sessions_workspace_active_idx ON knowledge.learning_sessions(workspace_id,occurred_at DESC,id) WHERE deleted_at IS NULL;
CREATE INDEX runs_workspace_active_idx ON knowledge.experiment_runs(workspace_id,created_at DESC,id) WHERE deleted_at IS NULL;
ALTER TABLE knowledge.background_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge.background_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY job_workspace_isolation ON knowledge.background_jobs
    USING (workspace_id = NULLIF(current_setting('app.workspace_id',true),'')::uuid
           OR current_setting('app.system',true) = 'jobs')
    WITH CHECK (workspace_id = NULLIF(current_setting('app.workspace_id',true),'')::uuid
                OR current_setting('app.system',true) = 'jobs');
INSERT INTO knowledge.schema_migrations(version) VALUES ('V009');
COMMIT;
