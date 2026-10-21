BEGIN;

CREATE TABLE knowledge.learning_paths (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL CHECK (length(trim(title)) > 0),
    objective_md text NOT NULL DEFAULT '',
    description_md text NOT NULL DEFAULT '',
    completion_criteria_md text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
    share_token text UNIQUE,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CHECK ((status = 'published' AND share_token IS NOT NULL) OR
           (status = 'draft' AND share_token IS NULL))
);
CREATE INDEX learning_paths_active_idx ON knowledge.learning_paths(updated_at)
    WHERE deleted_at IS NULL;

CREATE TABLE knowledge.learning_path_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    path_id uuid NOT NULL REFERENCES knowledge.learning_paths(id) ON DELETE CASCADE,
    object_id uuid REFERENCES knowledge.objects(id) ON DELETE SET NULL,
    position integer NOT NULL CHECK (position >= 0),
    title text NOT NULL CHECK (length(trim(title)) > 0),
    guidance_md text NOT NULL DEFAULT '',
    completion_criteria_md text NOT NULL DEFAULT '',
    estimated_minutes integer CHECK (estimated_minutes >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(path_id, position)
);
CREATE INDEX learning_path_steps_object_idx ON knowledge.learning_path_steps(object_id);

INSERT INTO knowledge.schema_migrations(version) VALUES ('V004');
COMMIT;
