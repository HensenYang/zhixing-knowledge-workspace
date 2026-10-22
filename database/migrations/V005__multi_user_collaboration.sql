BEGIN;

CREATE TABLE knowledge.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE NOT NULL CHECK (position('@' in email) > 1),
    display_name text NOT NULL CHECK (length(trim(display_name)) > 0),
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE knowledge.workspaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL CHECK (length(trim(name)) > 0),
    created_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE knowledge.workspace_members (
    workspace_id uuid NOT NULL REFERENCES knowledge.workspaces(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES knowledge.users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('owner','editor','reviewer','viewer')),
    joined_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id,user_id)
);

CREATE TABLE knowledge.auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES knowledge.users(id) ON DELETE CASCADE,
    token_hash text UNIQUE NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX auth_sessions_expiry_idx ON knowledge.auth_sessions(expires_at);

INSERT INTO knowledge.workspaces(name) VALUES ('原有知识空间');

ALTER TABLE knowledge.objects ADD COLUMN workspace_id uuid REFERENCES knowledge.workspaces(id),
    ADD COLUMN created_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    ADD COLUMN updated_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;
ALTER TABLE knowledge.relations ADD COLUMN workspace_id uuid REFERENCES knowledge.workspaces(id),
    ADD COLUMN created_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    ADD COLUMN updated_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;
ALTER TABLE knowledge.canvases ADD COLUMN workspace_id uuid REFERENCES knowledge.workspaces(id),
    ADD COLUMN created_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    ADD COLUMN updated_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;
ALTER TABLE knowledge.learning_sessions ADD COLUMN workspace_id uuid REFERENCES knowledge.workspaces(id),
    ADD COLUMN created_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    ADD COLUMN updated_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;
ALTER TABLE knowledge.experiment_runs ADD COLUMN workspace_id uuid REFERENCES knowledge.workspaces(id),
    ADD COLUMN created_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    ADD COLUMN updated_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;
ALTER TABLE knowledge.attachments ADD COLUMN workspace_id uuid REFERENCES knowledge.workspaces(id),
    ADD COLUMN created_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;
ALTER TABLE knowledge.source_imports ADD COLUMN workspace_id uuid REFERENCES knowledge.workspaces(id);
ALTER TABLE knowledge.learning_paths ADD COLUMN workspace_id uuid REFERENCES knowledge.workspaces(id),
    ADD COLUMN created_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    ADD COLUMN updated_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;
ALTER TABLE knowledge.object_revisions ADD COLUMN author_id uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;
ALTER TABLE knowledge.canvas_revisions ADD COLUMN author_id uuid REFERENCES knowledge.users(id) ON DELETE SET NULL;

UPDATE knowledge.objects SET workspace_id=(SELECT id FROM knowledge.workspaces LIMIT 1);
UPDATE knowledge.relations SET workspace_id=(SELECT id FROM knowledge.workspaces LIMIT 1);
UPDATE knowledge.canvases SET workspace_id=(SELECT id FROM knowledge.workspaces LIMIT 1);
UPDATE knowledge.learning_sessions SET workspace_id=(SELECT id FROM knowledge.workspaces LIMIT 1);
UPDATE knowledge.experiment_runs SET workspace_id=(SELECT id FROM knowledge.workspaces LIMIT 1);
UPDATE knowledge.attachments SET workspace_id=(SELECT id FROM knowledge.workspaces LIMIT 1);
UPDATE knowledge.source_imports SET workspace_id=(SELECT id FROM knowledge.workspaces LIMIT 1);
UPDATE knowledge.learning_paths SET workspace_id=(SELECT id FROM knowledge.workspaces LIMIT 1);

ALTER TABLE knowledge.objects ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE knowledge.relations ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE knowledge.canvases ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE knowledge.learning_sessions ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE knowledge.experiment_runs ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE knowledge.attachments ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE knowledge.source_imports ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE knowledge.learning_paths ALTER COLUMN workspace_id SET NOT NULL;

ALTER TABLE knowledge.source_imports DROP CONSTRAINT source_imports_source_type_source_key_key;
ALTER TABLE knowledge.source_imports ADD UNIQUE(workspace_id,source_type,source_key);

CREATE TABLE knowledge.comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES knowledge.workspaces(id) ON DELETE CASCADE,
    target_type text NOT NULL CHECK (target_type IN ('object','relation','canvas','session','run')),
    target_id uuid NOT NULL,
    author_id uuid NOT NULL REFERENCES knowledge.users(id) ON DELETE CASCADE,
    parent_id uuid REFERENCES knowledge.comments(id) ON DELETE CASCADE,
    body text NOT NULL CHECK (length(trim(body)) > 0),
    resolved_at timestamptz,
    resolved_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX comments_target_idx ON knowledge.comments(workspace_id,target_type,target_id,created_at);

CREATE TABLE knowledge.review_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES knowledge.workspaces(id) ON DELETE CASCADE,
    target_type text NOT NULL CHECK (target_type IN ('object','relation','canvas','session','run')),
    target_id uuid NOT NULL,
    target_version integer NOT NULL CHECK (target_version > 0),
    requested_by uuid NOT NULL REFERENCES knowledge.users(id) ON DELETE CASCADE,
    reviewed_by uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','changes_requested')),
    note text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz
);
CREATE INDEX review_requests_target_idx ON knowledge.review_requests(workspace_id,target_type,target_id,created_at DESC);

CREATE TABLE knowledge.activity_events (
    id bigserial PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES knowledge.workspaces(id) ON DELETE CASCADE,
    actor_id uuid REFERENCES knowledge.users(id) ON DELETE SET NULL,
    action text NOT NULL,
    target_type text,
    target_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX activity_workspace_idx ON knowledge.activity_events(workspace_id,id DESC);

CREATE OR REPLACE FUNCTION knowledge.collaboration_defaults() RETURNS trigger AS $$
DECLARE
    active_workspace uuid := NULLIF(current_setting('app.workspace_id',true),'')::uuid;
    active_user uuid := NULLIF(current_setting('app.user_id',true),'')::uuid;
BEGIN
    IF TG_OP='INSERT' THEN
        NEW.workspace_id := COALESCE(NEW.workspace_id,active_workspace);
        IF to_jsonb(NEW) ? 'created_by' THEN NEW.created_by := COALESCE(NEW.created_by,active_user); END IF;
    END IF;
    IF to_jsonb(NEW) ? 'updated_by' THEN NEW.updated_by := active_user; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER objects_collaboration_defaults BEFORE INSERT OR UPDATE ON knowledge.objects FOR EACH ROW EXECUTE FUNCTION knowledge.collaboration_defaults();
CREATE TRIGGER relations_collaboration_defaults BEFORE INSERT OR UPDATE ON knowledge.relations FOR EACH ROW EXECUTE FUNCTION knowledge.collaboration_defaults();
CREATE TRIGGER canvases_collaboration_defaults BEFORE INSERT OR UPDATE ON knowledge.canvases FOR EACH ROW EXECUTE FUNCTION knowledge.collaboration_defaults();
CREATE TRIGGER sessions_collaboration_defaults BEFORE INSERT OR UPDATE ON knowledge.learning_sessions FOR EACH ROW EXECUTE FUNCTION knowledge.collaboration_defaults();
CREATE TRIGGER runs_collaboration_defaults BEFORE INSERT OR UPDATE ON knowledge.experiment_runs FOR EACH ROW EXECUTE FUNCTION knowledge.collaboration_defaults();
CREATE TRIGGER attachments_collaboration_defaults BEFORE INSERT OR UPDATE ON knowledge.attachments FOR EACH ROW EXECUTE FUNCTION knowledge.collaboration_defaults();
CREATE TRIGGER source_imports_collaboration_defaults BEFORE INSERT OR UPDATE ON knowledge.source_imports FOR EACH ROW EXECUTE FUNCTION knowledge.collaboration_defaults();
CREATE TRIGGER learning_paths_collaboration_defaults BEFORE INSERT OR UPDATE ON knowledge.learning_paths FOR EACH ROW EXECUTE FUNCTION knowledge.collaboration_defaults();

CREATE OR REPLACE FUNCTION knowledge.revision_author() RETURNS trigger AS $$
BEGIN
    NEW.author_id := COALESCE(NEW.author_id,NULLIF(current_setting('app.user_id',true),'')::uuid);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER object_revision_author BEFORE INSERT ON knowledge.object_revisions FOR EACH ROW EXECUTE FUNCTION knowledge.revision_author();
CREATE TRIGGER canvas_revision_author BEFORE INSERT ON knowledge.canvas_revisions FOR EACH ROW EXECUTE FUNCTION knowledge.revision_author();

-- Runtime requests set app.workspace_id inside each transaction.  RLS keeps
-- accidental unscoped queries from crossing workspace boundaries.
DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['objects','relations','canvases','learning_sessions','experiment_runs','attachments','source_imports','comments','review_requests','activity_events']
    LOOP
        EXECUTE format('ALTER TABLE knowledge.%I ENABLE ROW LEVEL SECURITY',table_name);
        EXECUTE format('ALTER TABLE knowledge.%I FORCE ROW LEVEL SECURITY',table_name);
        EXECUTE format(
            'CREATE POLICY workspace_isolation ON knowledge.%I USING (workspace_id = NULLIF(current_setting(''app.workspace_id'',true),'''')::uuid) WITH CHECK (workspace_id = NULLIF(current_setting(''app.workspace_id'',true),'''')::uuid)',
            table_name
        );
    END LOOP;
END $$;

INSERT INTO knowledge.schema_migrations(version) VALUES ('V005');
COMMIT;
