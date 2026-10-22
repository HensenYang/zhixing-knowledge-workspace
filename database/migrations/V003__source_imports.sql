BEGIN;
CREATE TABLE knowledge.source_imports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type text NOT NULL CHECK (source_type IN ('arxiv','doi','github','pdf','mcp')),
    source_key text NOT NULL,
    source_url text,
    original_name text,
    extracted_metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(extracted_metadata) = 'object'),
    object_id uuid REFERENCES knowledge.objects(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(source_type, source_key)
);
CREATE INDEX source_imports_object_idx ON knowledge.source_imports(object_id);
INSERT INTO knowledge.schema_migrations(version) VALUES ('V003');
COMMIT;
