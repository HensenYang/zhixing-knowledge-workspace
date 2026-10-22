BEGIN;
-- Foreign keys do not get indexes automatically; these serve joins, cascades and the list queries.
CREATE INDEX IF NOT EXISTS relation_evidence_relation_idx ON knowledge.relation_evidence(relation_id);
CREATE INDEX IF NOT EXISTS relation_evidence_object_idx ON knowledge.relation_evidence(evidence_object_id) WHERE evidence_object_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS object_tags_tag_idx ON knowledge.object_tags(tag_id);
CREATE INDEX IF NOT EXISTS session_objects_object_idx ON knowledge.session_objects(object_id);
CREATE INDEX IF NOT EXISTS experiment_runs_experiment_idx ON knowledge.experiment_runs(experiment_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS run_artifacts_run_idx ON knowledge.run_artifacts(run_id);
CREATE INDEX IF NOT EXISTS canvas_items_object_idx ON knowledge.canvas_items(object_id) WHERE object_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS canvas_edges_canvas_idx ON knowledge.canvas_edges(canvas_id);
CREATE INDEX IF NOT EXISTS canvas_edges_relation_idx ON knowledge.canvas_edges(relation_id) WHERE relation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS object_attachments_attachment_idx ON knowledge.object_attachments(attachment_id);

-- Active-row indexes for the graph expansion and the paged lists.
CREATE INDEX IF NOT EXISTS relations_source_active_idx ON knowledge.relations(source_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS relations_target_active_idx ON knowledge.relations(target_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS relations_created_active_idx ON knowledge.relations(created_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS sessions_active_idx ON knowledge.learning_sessions(occurred_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS runs_active_idx ON knowledge.experiment_runs(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS canvases_active_idx ON knowledge.canvases(updated_at DESC) WHERE deleted_at IS NULL;

-- The trash lists only rows that carry a deletion time.
CREATE INDEX IF NOT EXISTS objects_trash_idx ON knowledge.objects(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS relations_trash_idx ON knowledge.relations(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS canvases_trash_idx ON knowledge.canvases(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS sessions_trash_idx ON knowledge.learning_sessions(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS runs_trash_idx ON knowledge.experiment_runs(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS attachments_trash_idx ON knowledge.attachments(deleted_at) WHERE deleted_at IS NOT NULL;

-- Substring search (ILIKE '%text%') uses trigram indexes. pg_trgm is optional: if it cannot be
-- installed (missing contrib package or privileges) the search still works, just without the index.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE INDEX IF NOT EXISTS objects_title_trgm_idx ON knowledge.objects USING gin (title gin_trgm_ops);
    CREATE INDEX IF NOT EXISTS objects_body_trgm_idx ON knowledge.objects USING gin (body_md gin_trgm_ops);
    CREATE INDEX IF NOT EXISTS tags_name_trgm_idx ON knowledge.tags USING gin (name gin_trgm_ops);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pg_trgm indexes skipped: %', SQLERRM;
END
$$;

INSERT INTO knowledge.schema_migrations(version) VALUES ('V006');
COMMIT;
