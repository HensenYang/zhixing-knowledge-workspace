BEGIN;
-- Long-running work (backup restore, link checks) runs in the background and reports here.
CREATE TABLE knowledge.background_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed')),
    progress integer NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    message text NOT NULL DEFAULT '',
    result jsonb,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz
);
CREATE INDEX background_jobs_recent_idx ON knowledge.background_jobs(kind, created_at DESC);
INSERT INTO knowledge.schema_migrations(version) VALUES ('V007');
COMMIT;
