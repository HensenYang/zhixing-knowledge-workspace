BEGIN;
ALTER TABLE knowledge.objects ADD COLUMN deleted_at timestamptz;
ALTER TABLE knowledge.relations ADD COLUMN deleted_at timestamptz;
ALTER TABLE knowledge.canvases ADD COLUMN deleted_at timestamptz;
ALTER TABLE knowledge.learning_sessions ADD COLUMN deleted_at timestamptz,
    ADD COLUMN version integer NOT NULL DEFAULT 1,
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE knowledge.experiment_runs ADD COLUMN deleted_at timestamptz,
    ADD COLUMN version integer NOT NULL DEFAULT 1,
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE knowledge.attachments ADD COLUMN deleted_at timestamptz;
CREATE INDEX objects_active_idx ON knowledge.objects(updated_at) WHERE deleted_at IS NULL;
INSERT INTO knowledge.schema_migrations(version) VALUES ('V002');
COMMIT;
