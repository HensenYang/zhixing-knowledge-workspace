# Engineering and Scaling (P2) and Evidence Health Checks (P1)

[Chinese version](engineering-and-evidence-health-zh.md)

Status: implemented on `main` (personal edition). All 74 backend tests and 17 browser end-to-end tests passed. A fresh database can migrate through V008.

## 1. Backend structure (`app.py` was not split in this iteration)

Teammates' branches for sharing and import/export, LLM, Zotero, multiple users, and learning paths also make extensive changes to `backend/app.py`. To reduce merge conflicts, this iteration **keeps `app.py` intact**, placing new capabilities in separate modules and making only localized changes to the existing file:

```text
backend/
  app.py              Existing routes; changes for pooling, pagination, batch queries,
                      graph neighborhoods, and asynchronous backup restore
  pool.py             Database connection pool
  paging.py           limit/offset validation and X-Total-Count
  jobs.py             Background jobs (/api/jobs)
  link_checker.py     Safe link checker
  evidence_health.py  Evidence health checks (/api/evidence-health)
```

Splitting the backend into modules is deferred until teammates' branches have merged into `main`. Coordinate the refactor and announce it first to avoid simultaneous edits to the same file.

## 2. Database connection pool

- Previously, every request created a PostgreSQL connection. A small pool in `backend/pool.py`, used by `db()` in `backend/app.py`, now reuses idle connections. At most `DB_POOL_SIZE` connections are in use at once, with a default of 10. Requests queue for up to 10 seconds when the pool is full, then return 503 on timeout, absorbing short concurrency spikes.
- Connections idle for more than five minutes are discarded. Stale connections after a database restart are discarded and replaced, with one retry. If the database is down, connection failure is reported immediately rather than waiting unnecessarily.
- Connections use `application_name = zhixing-workspace` so they are easy to identify in `pg_stat_activity`.
- psycopg2's built-in pool was not used because setting `minconn` to 0 causes returned connections to close immediately, defeating reuse.

## 3. Query optimization and indexes

- **N+1 queries:** note tags, relation evidence, objects linked to learning logs, run artifacts, and checks for deleted canvas relations previously required an extra query for each list row. Each now uses one batch query. Tests assert that list endpoints use a fixed three queries regardless of data volume.
- **Graph:** `/api/graph?center=&depth=` previously loaded every node and relation into memory before filtering. It now expands neighborhoods layer by layer in the database and reads only the relevant neighborhood. Without a center, it returns up to `limit` nodes with the most connections, defaulting to 1000. `X-Total-Count` reports the total, and the page indicates when only a subset is displayed. Browser layout slows sharply with node count: measurements showed about 15 seconds for 1000 nodes and two seconds for 300. The global graph page therefore requests only the 300 most connected nodes; a local graph around a note is not subject to that same cap. Tests compare neighborhood results against a brute-force breadth-first search.
- **Indexes (migration V006):** PostgreSQL does not automatically index foreign key columns. Columns such as `relation_evidence.relation_id` and `canvas_edges.canvas_id` lacked indexes. The migration also adds partial indexes for records that are not deleted and indexes for the trash.
- **Search:** `%` and `_` in search terms were previously interpreted as wildcards, so a search such as “100%” produced overly broad matches. They are now matched literally.
- **Text search indexes:** `pg_trgm` trigram indexes have been added. If the extension cannot be installed, the migration skips them instead of failing. **Caveat:** trigram generation depends on character classification in the database locale. A database using the `C` locale does not generate trigrams for Chinese characters, so these indexes do not accelerate Chinese searches in that environment, including our test database. Measured Chinese searches across 5000 notes already took about 25–30 ms.

## 4. Pagination conventions

List endpoints continue returning ordinary JSON arrays for frontend compatibility. Totals are provided in the `X-Total-Count` response header, with `limit` and `offset` parameters:

| Endpoint | Default limit | Maximum |
|---|---|---|
| `/api/objects` | 200 | 1000 |
| `/api/relations` | 5000 | 20000 |
| `/api/sessions`, `/api/runs`, `/api/canvases`, `/api/trash` | 200 | 1000 |
| `/api/graph` (node count; the global graph page requests 300) | 1000 | 5000 |

UI behavior: knowledge and materials show 24 items per page; trash shows 50 and returns to the previous page when the current one becomes empty; the timeline starts with the latest 200 entries and can load 200 more; the home page requests only three or four rows and the relevant totals.

**Known limit:** relation selectors, the graph page, and canvases still read at most 1000 notes and all relations in one request. Selectors cannot show every note beyond that scale. This is a frontend limit, not a backend limit.

## 5. Background jobs

- Backup restore previously ran synchronously inside the request, with a maximum backup size of 128 MB, leaving the page waiting until completion or timeout. Backup validation and ID conflict detection remain synchronous, with conflicts returning 409 immediately. After validation, the API creates a background job and returns **202 + job_id**. Settings polls `/api/jobs/{id}` for progress; leaving and returning to the page resumes the display.
- The `background_jobs` table, introduced in V007, stores status, progress, results, and errors. One worker processes restore jobs sequentially. Link checking has its own thread because external sites can take minutes to respond, so it does not block restores. On service restart, unfinished jobs are marked failed with a message that the restart interrupted them, rather than remaining in progress indefinitely.
- Restore remains transactional: on failure, database changes roll back and newly written attachment files are removed. Tests cover this behavior.
- The evidence health page's link checker uses the same job mechanism.

## 6. Measurements

On the same machine, `scripts/seed_scale_data.py` generated 5000 notes, 15,000 relations with evidence on 60%, and 500 learning logs and runs. The original code from the archive was compared with the updated code. Each endpoint was measured three to five times, taking the median, with **equal response data volumes**:

| Endpoint | Original | Updated | Speedup |
|---|---|---|---|
| Note list, 200 items | 28 ms | 11 ms | 2.4× |
| Note list, 1000 items | 110 ms | 41 ms | 2.7× |
| All relations (15,000) | 4192 ms | 379 ms | 11× |
| All learning logs (500) | 35 ms | 15 ms | 2.3× |
| All runs (500) | 65 ms | 28 ms | 2.3× |
| Local graph (center node, two hops) | 110 ms | 47 ms | 2.4× |
| Full graph, 5000 nodes | 271 ms | 296 ms | No improvement |
| 40 concurrent readers | 435 requests/s | 729 requests/s | 1.7× |

The full graph did not improve at an equal node count because serializing roughly 5 MB dominated its response time. Its benefit comes from returning only 1000 nodes by default: about 55 ms and 0.8 MB, compared with the original 271 ms and 5.3 MB. All nine evidence health checks together took about 130 ms on the same dataset.

Measurements used a Mac with PostgreSQL 17 over a loopback connection. These figures compare the two versions and do not predict performance on other machines. To reproduce:

```powershell
$env:DATABASE_URL = "TEST_DATABASE_URL"
python scripts/seed_scale_data.py --schema bench --objects 5000
# Start the backend with KNOWLEDGE_SCHEMA=bench, then:
python scripts/benchmark_api.py http://127.0.0.1:8001
```

After reorganizing the modules into their current structure, the updated version was measured again with the same scripts and data volume: 11 ms for the first 200 notes, 135 ms for all 15,000 relations, 54 ms for the default 1000-node graph (0.8 MB), and 759 requests/s with 40 concurrent readers. The overall performance pattern remained consistent with the table.

## 7. Tests and CI

- The backend `client` fixture in `backend/tests/conftest.py` creates a separate schema and attachment directory for each test and removes them afterward. `TEST_DATABASE_URL` must point to an isolated test database.
- Added tests cover query counts, pagination, graph neighborhoods compared with brute-force search, connection pooling (reuse, waiting, expiry, recovery from terminated connections, and concurrency limits), background jobs (progress, failure, restart recovery, attachment cleanup, and slow link checks not blocking restores), the link checker, each evidence health check, and migration conventions.
- **Migration convention tests:** version numbers must be unique, filenames must follow `V###__snake_name.sql`, and each migration must register its own version. This iteration uses V006–V008 because teammates' branches use V003–V005. Future version collisions can therefore fail checks before merging.
- End-to-end tests: `python scripts/run_e2e.py [Playwright arguments]` creates a temporary schema in the test database, starts the backend on 8002 and frontend on 5175, and removes the schema afterward. **Production data is not touched.** Tests within a run share the temporary database, so new assertions account for totals rather than assuming an empty database.
- CI in `.github/workflows/ci.yml` covers the backend (pyflakes, pytest, and fresh database migrations), frontend build, and browser end-to-end tests using a PostgreSQL service container. GitHub Actions was not run locally for this implementation; the first hosted run may require minor adjustments.

## 8. Evidence health checks

The “Evidence health” page uses `GET /api/evidence-health` for the overview, `GET /api/evidence-health/{check}` for paginated details, and `POST /api/evidence-health/link-check` for background link checks. Audits are read-only with respect to knowledge records and count only records that are neither deleted nor archived.

| Check | Severity | Rule |
|---|---|---|
| Problematic evidence | Error | Evidence points to a deleted note, or its source URL is not HTTP(S) |
| Broken links | Error | Link checking returns 404/410, DNS resolution fails, or the connection fails |
| Relations without evidence | Warning | A relation has no evidence rows |
| Unverified experiment claims | Warning | An experiment supports, questions, or evaluates an object without a successful run; or mastery is marked as able to implement/reproduce without a linked successful experiment |
| Non-reproducible runs | Warning | A successful run lacks a command, code commit, configuration, or metrics; or a failed run lacks a failure reason |
| Possibly outdated sources | Warning / Info | A source note's `verified_on` is older than the configured threshold (warning), or is missing (info) |
| Dependency cycles | Warning | Dependency relations form a cycle; identify strongly connected components and show a concrete cycle |
| Evidence without a locator | Info | A relation has evidence, but none includes a page, chapter, or line locator |
| Conclusions both supported and questioned | Info | The same object is both supported and questioned |

Results on the Unitree case collection: 48 of 91 relations had no evidence, giving 47.3% coverage; 43 evidence entries lacked locators; three experiment claims had no successful run; and four objects were both supported and questioned.

**Link checker design:** the checker requests external URLs from notes and evidence. Since notes may be imported, links must not become a way to probe the local machine or private network. Before each request, resolve the hostname and refuse the request if any address is not public, including loopback, private, link-local addresses such as 169.254.169.254, and shared address ranges. Connect to the validated IP while retaining the original hostname for the Host header and TLS verification to prevent DNS rebinding. Revalidate every redirect hop.

404/410 and connection failures count as broken links. 401/403/429/5xx are indeterminate rather than broken. If the vast majority of connections fail, treat this as a local network problem and do not save the results. The checker has been verified against real GitHub, arXiv, and Hugging Face URLs. URLs checked within 24 hours are cached unless the user chooses to recheck all links.

**Limitations:** rules detect structural issues, such as dependency cycles or an object being both supported and questioned. They cannot detect semantic contradictions between two sources. Those require human judgment or future AI assistance; the supported-and-questioned list provides an entry point for manual review.

## 9. Known limitations

- Frontend selectors and the graph page have a 1000-note limit; see section 4.
- Chinese search does not rely on indexes in the tested environment; see section 3.
- Background jobs use in-process worker threads: one for restore and one for link checking. This supports a single machine with a single process. Do not run multiple uvicorn workers, because each process marks in-progress jobs as interrupted at startup.
- The `link_checks` table is keyed by URL and stores only public URL reachability results.

## 10. Integration with multi-user main (2026-10-23)

- The other branch has its own V003–V005 migrations. These changes use V006–V008 to avoid version collisions.
- V009 adds `workspace_id` and `created_by` to `background_jobs`, defaulting to the current transaction's request context, and enables and forces row-level security. Startup recovery uses the transaction-local marker `app.system='jobs'`. Legacy jobs with unknown ownership are neither assigned to arbitrary users nor exposed to users. Workspace-first list indexes were added for objects, relations, canvases, learning logs, and experiment runs.
- Both `db()` and authentication's `raw_db()` use the connection pool while retaining transaction-local `app.workspace_id` and `app.user_id`. Background threads copy the request context. Trash pagination retains workspace filtering for learning paths.
- Main's source import/export, learning paths, team collaboration, and Chinese/English interface are preserved. Evidence health, pagination, graph truncation notices, and background restore progress all have bilingual messages.
- Database tests must use a non-superuser connection so row-level security takes effect.
