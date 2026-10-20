-- PostgreSQL 18 schema verified on an isolated local test instance.
-- Not yet applied to the user's primary PostgreSQL service.
-- Apply only inside the independent embodied_knowledge database.
BEGIN;
CREATE SCHEMA knowledge;

CREATE TABLE knowledge.objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL CHECK (kind IN ('concept','resource','repository','model','dataset','benchmark','experiment','question','task')),
    title text NOT NULL CHECK (length(trim(title)) > 0),
    summary text NOT NULL DEFAULT '',
    body_md text NOT NULL DEFAULT '',
    source_url text,
    reading_status text NOT NULL DEFAULT 'unread' CHECK (reading_status IN ('unread','skimming','reading','organized')),
    mastery_status text NOT NULL DEFAULT 'unknown' CHECK (mastery_status IN ('unknown','explain','implement','reproduce','analyze')),
    metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object'),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    archived_at timestamptz
);
CREATE INDEX objects_kind_idx ON knowledge.objects(kind);
CREATE TABLE knowledge.tags (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text UNIQUE NOT NULL);
CREATE TABLE knowledge.object_tags (
    object_id uuid NOT NULL REFERENCES knowledge.objects(id) ON DELETE CASCADE,
    tag_id uuid NOT NULL REFERENCES knowledge.tags(id) ON DELETE CASCADE,
    PRIMARY KEY(object_id, tag_id)
);

CREATE TABLE knowledge.relations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES knowledge.objects(id) ON DELETE RESTRICT,
    target_id uuid NOT NULL REFERENCES knowledge.objects(id) ON DELETE RESTRICT,
    relation_type text NOT NULL CHECK (relation_type IN ('depends_on','implements','uses','evaluates','supports','questions','compares_with','related_to')),
    description text NOT NULL DEFAULT '',
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (source_id <> target_id),
    CHECK (relation_type NOT IN ('compares_with','related_to') OR source_id < target_id),
    UNIQUE(source_id, target_id, relation_type)
);
CREATE INDEX relations_target_idx ON knowledge.relations(target_id);
CREATE TABLE knowledge.relation_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relation_id uuid NOT NULL REFERENCES knowledge.relations(id) ON DELETE CASCADE,
    evidence_object_id uuid REFERENCES knowledge.objects(id) ON DELETE RESTRICT,
    source_url text,
    locator text NOT NULL DEFAULT '',
    explanation text NOT NULL DEFAULT '',
    CHECK (evidence_object_id IS NOT NULL OR source_url IS NOT NULL)
);

CREATE TABLE knowledge.canvases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    viewport jsonb NOT NULL DEFAULT '{"x":0,"y":0,"zoom":1}',
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE knowledge.canvas_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canvas_id uuid NOT NULL REFERENCES knowledge.canvases(id) ON DELETE CASCADE,
    item_type text NOT NULL CHECK (item_type IN ('object','text','group')),
    object_id uuid REFERENCES knowledge.objects(id) ON DELETE RESTRICT,
    parent_id uuid,
    x double precision NOT NULL DEFAULT 0,
    y double precision NOT NULL DEFAULT 0,
    width double precision NOT NULL DEFAULT 260 CHECK (width > 0),
    height double precision NOT NULL DEFAULT 160 CHECK (height > 0),
    properties jsonb NOT NULL DEFAULT '{}',
    UNIQUE(canvas_id,id),
    FOREIGN KEY(canvas_id,parent_id) REFERENCES knowledge.canvas_items(canvas_id,id) DEFERRABLE INITIALLY DEFERRED,
    CHECK (parent_id IS NULL OR parent_id <> id),
    CHECK ((item_type = 'object' AND object_id IS NOT NULL) OR (item_type <> 'object' AND object_id IS NULL))
);
CREATE TABLE knowledge.canvas_edges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canvas_id uuid NOT NULL REFERENCES knowledge.canvases(id) ON DELETE CASCADE,
    source_item_id uuid NOT NULL,
    target_item_id uuid NOT NULL,
    relation_id uuid REFERENCES knowledge.relations(id) ON DELETE SET NULL,
    label text NOT NULL DEFAULT '',
    properties jsonb NOT NULL DEFAULT '{}',
    FOREIGN KEY(canvas_id,source_item_id) REFERENCES knowledge.canvas_items(canvas_id,id) ON DELETE CASCADE,
    FOREIGN KEY(canvas_id,target_item_id) REFERENCES knowledge.canvas_items(canvas_id,id) ON DELETE CASCADE,
    CHECK (source_item_id <> target_item_id)
);
-- API additionally validates group-only parents, acyclic groups, and matching
-- object endpoints when a canvas edge references a knowledge relation.

CREATE TABLE knowledge.learning_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    objective text NOT NULL,
    activity_md text NOT NULL DEFAULT '',
    understanding_change_md text NOT NULL DEFAULT '',
    blockers_md text NOT NULL DEFAULT '',
    next_step_md text NOT NULL DEFAULT '',
    duration_minutes integer CHECK (duration_minutes >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_occurred_idx ON knowledge.learning_sessions(occurred_at);
CREATE TABLE knowledge.session_objects (
    session_id uuid NOT NULL REFERENCES knowledge.learning_sessions(id) ON DELETE CASCADE,
    object_id uuid NOT NULL REFERENCES knowledge.objects(id) ON DELETE RESTRICT,
    PRIMARY KEY(session_id,object_id)
);

CREATE TABLE knowledge.experiment_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id uuid NOT NULL REFERENCES knowledge.objects(id) ON DELETE RESTRICT,
    started_at timestamptz,
    ended_at timestamptz,
    status text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','running','succeeded','failed','cancelled')),
    hypothesis_md text NOT NULL DEFAULT '',
    command text NOT NULL DEFAULT '',
    git_commit text,
    weight_version text,
    dataset_version text,
    config jsonb NOT NULL DEFAULT '{}',
    environment jsonb NOT NULL DEFAULT '{}',
    metrics jsonb NOT NULL DEFAULT '{}',
    seed bigint,
    result_md text NOT NULL DEFAULT '',
    failure_md text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);
-- API requires experiment_id to reference an object of kind experiment.
CREATE TABLE knowledge.run_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES knowledge.experiment_runs(id) ON DELETE CASCADE,
    artifact_type text NOT NULL,
    location text NOT NULL,
    sha256 text,
    included_in_backup boolean NOT NULL DEFAULT false
);

CREATE TABLE knowledge.attachments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    original_name text NOT NULL,
    relative_path text UNIQUE NOT NULL,
    mime_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    sha256 text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE knowledge.object_attachments (
    object_id uuid NOT NULL REFERENCES knowledge.objects(id) ON DELETE CASCADE,
    attachment_id uuid NOT NULL REFERENCES knowledge.attachments(id) ON DELETE RESTRICT,
    PRIMARY KEY(object_id,attachment_id)
);
CREATE TABLE knowledge.object_revisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    object_id uuid NOT NULL REFERENCES knowledge.objects(id) ON DELETE CASCADE,
    version integer NOT NULL,
    snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(object_id,version)
);
CREATE TABLE knowledge.canvas_revisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canvas_id uuid NOT NULL REFERENCES knowledge.canvases(id) ON DELETE CASCADE,
    version integer NOT NULL,
    snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(canvas_id,version)
);
CREATE TABLE knowledge.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO knowledge.schema_migrations(version) VALUES ('V001');
-- Service transactions increment version and updated_at and store revisions.
-- Export includes all tables plus attachments and an external-artifact manifest.
COMMIT;
