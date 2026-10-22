BEGIN;
-- Result of the last reachability check for every external URL used by a note or as evidence.
-- ok: true = reachable, false = gone, NULL = could not tell (login wall, rate limit, server error, private address).
-- `error` is a machine-readable code (not_found, dns_failed, timeout, ...), shown in the user's language by the interface.
-- The table is keyed by URL and holds nothing but public reachability; the interface only ever reads it through a join
-- with the notes and evidence that use the URL.
CREATE TABLE knowledge.link_checks (
    url text PRIMARY KEY,
    status_code integer,
    ok boolean,
    error text,
    final_url text,
    checked_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX link_checks_failed_idx ON knowledge.link_checks(checked_at) WHERE ok IS FALSE;
INSERT INTO knowledge.schema_migrations(version) VALUES ('V008');
COMMIT;
