# Embodied Intelligence Knowledge Workspace: Phase 1 Specification

[Chinese version](phase-1-design-zh.md)

Date: 2026-09-30; implementation and verification updated on 2026-10-01. Status: the first version has been implemented and accepted against a separate PostgreSQL test database. The user has initialized and started the production database; the production API reports `database=ready` and `schema_version=V001`, and the frontend returns HTTP 200. Follow the README for first-use interaction acceptance checks.

## Confirmed usage conditions

- Access through a local browser, for individual use. This project is independent of UNSW_Helper.
- The user has experience training and reproducing models with PyTorch. The learning focus is robotic manipulation, VLA, and world models.
- Windows host reporting version 10.0.26200; the exact Windows product name remains to be confirmed.
- `nvidia-smi`: RTX 4090, 24564 MiB VRAM, driver 610.47.
- No robot or dedicated server is available. Start with local offline inference and simulation.
- No fixed weekly hours are required. Progress is determined by stage completion criteria. Tasks may include an estimated duration, but this is optional.
- PostgreSQL client 18.3 is installed at `A:/PostgreSQL`. The default port did not respond during the first check. On rechecking, `postgresql-x64-18` was Running and `127.0.0.1:5432` accepted connections. Authentication and application database connectivity had not yet been tested at that point; service readiness does not establish a verified application connection.

## Technology choices and evidence

Reference project: `A:/WeChat_Mini_programs/UNSW_Helper`.

- `frontend_Web/package.json` and `src/App.jsx`: JavaScript/JSX, React 18, React Router 6, Vite 5, and Tailwind 3, with Tiptap for rich text editing.
- `frontend_Web/vite.config.js`: frontend development port 5173, with `/api` proxied to local port 8000.
- `backend/requirements.txt` and `src/db/connection.py`: Python, FastAPI, Pydantic, Uvicorn, and psycopg2; explicit SQL and a database connection pool.
- `database/flyway/sql`: versioned SQL migrations.

The new project uses JavaScript/JSX, React, Vite, Tailwind, and React Router; Python, FastAPI, Pydantic, and psycopg2; and PostgreSQL 18. A separate `.venv` was created with the existing Python 3.12.7 installation. Compatibility with the current dependencies has been verified, without changing the model environment.

JavaScript keeps the project consistent with the reference implementation. Pydantic and frontend JSDoc constrain object fields. Compatible dependency versions are pinned during installation rather than copying the reference project's entire dependency list.

React Flow (`@xyflow/react`) handles canvases, and Cytoscape.js handles the knowledge network. Markdown is the source format for the first version's body content, including equations and code blocks. Tiptap is deferred to avoid round trips between two formats.

Versioned SQL follows Flyway's filename convention, but installing Flyway is not required. Initially, migrations are applied in sequence through `psql`, with applied versions recorded.

## Project structure and runtime boundaries

```text
Model_Research/
  docs/                         Specifications, operating instructions, design decisions
  frontend_Web/
    src/components/             Editor, relation editor, graph, canvas, shared controls
    src/pages/                  Workspace, knowledge, graph, canvas, timeline, experiments, settings
    src/services/               API requests and response handling
    src/hooks/                  Autosave, queries, shortcuts
    src/utils/                  Graph conversion, import/export, formatting
    src/styles/                 Tailwind entry point and component styles
  backend/
    src/api/                    Objects, relations, canvases, logs, experiments, attachments, export
    src/core/                   Environment settings and logging
    src/db/                     Connections, explicit SQL repositories, transactions
    src/services/               Cross-table operations and backup/restore
  database/migrations/          Versioned SQL
  storage/attachments/          Small attachments; only relative paths are stored in the database
  storage/exports/              Export packages
  experiments/                 Experiment code and configuration; separate model environment
```

Recommended development ports are 5174 for the frontend and 8001 for the backend, avoiding the reference project's usual ports. Bind only to `127.0.0.1`; the frontend accesses the backend through the `/api` proxy. Report an explicit error if a development port is occupied.

Create a separate database named `embodied_knowledge`, with application schema `knowledge` and a dedicated application account. Do not reuse the reference project's database or copy its connection password.

Keep model weights and large datasets in separate directories. The workspace stores paths, versions, sizes, and optional checksums. Keep the model experiment environment separate from the knowledge workspace environment.

Configure database credentials in a local `.env` and commit `.env.example`. Credentials must not appear in the browser or documentation. Database creation and connectivity are the next runtime integration tasks in this specification.

## Page specification

The global layout has navigation on the left, the workspace in the center, collapsible details on the right, and global search and creation controls at the top. Desktop browsers take priority. The default theme is simple and suitable for sustained reading; the reference project's PlayStation visual style is not a requirement.

| Route | Default content | Core actions and completion criteria |
|---|---|---|
| `/` | Current questions, next tasks, recent activity, materials awaiting organization | Open current work from the home page without entering hours |
| `/knowledge` | Objects filtered by type, topic, and reading status | Create, search, archive, and open details |
| `/knowledge/:id` | Markdown body, properties, sources, backlinks, local graph | Preserve connections when renaming; inspect neighbors one or two hops away |
| `/graph` | Global knowledge network colored by type | Search, filter, expand, select nodes or edges, and edit relations |
| `/canvases` | Saved topic/question canvases | Create, rename, and open |
| `/canvases/:id` | Freeform canvas and a list of objects to drag in | Drag, zoom, group, connect, undo, and restore the layout after refresh |
| `/timeline` | Learning logs and experiment events | Inspect linked objects; record changes in understanding and next steps |
| `/experiments` | Experiments and runs organized by question | Record commands, configurations, versions, metrics, and failure reasons |
| `/settings` | Environment information, backup, and restore | Validate imports; restore a complete backup into a clean test database |

Every edit has an explicit saving, saved, or failed state. When the service is unavailable, retain the current draft and allow retries without reporting false success. Preview imports and check for ID conflicts before applying them. Prefer archiving; reserve permanent deletion for explicit cleanup.

## Objects and relations

Object types are `concept`, `resource`, `repository`, `model`, `dataset`, `benchmark`, `experiment`, `question`, and `task`.

Resource subtypes are `paper`, `blog`, `course`, and `documentation`. Logs and runs are stored separately and linked to objects.

Shared object fields include a UUID, title, Markdown body, description, reading status, mastery status, source URL, metadata, version, timestamps, and archive time.

Reading status and mastery status are separate: `unread/skimming/reading/organized` and `unknown/explain/implement/reproduce/analyze`.

Repository metadata includes a commit; model metadata includes the weights version and inputs/outputs; resource metadata includes DOI/arXiv identifiers, authors, year, and page notes; task metadata includes acceptance criteria. The API validates metadata by `kind`.

Relations are independent records with explicit direction. `A depends_on B` means A relies on B; a repository `implements` a resource; a run is associated with `evaluates` through an experiment object; results `supports/questions` a question or hypothesis.

Initial relation types are `depends_on`, `implements`, `uses`, `evaluates`, `supports`, `questions`, `compares_with`, and `related_to`. Display `compares_with` and `related_to` as undirected, and normalize endpoint order on write to prevent duplicates.

Relations may include evidence objects, page/chapter/line locators, and an explanation. Store multiple independent evidence entries in `relation_evidence`. Mastery status changes only through an explicit user action; viewing an object does not imply mastery.

## Canvas semantics

Knowledge objects and canvas instances are separate. An object may appear on multiple canvases, or more than once on the same canvas. Each instance has its own ID, position, size, and group.

A canvas item can be `object/text/group`. Object items reference an object ID; text and group items store their own content.

A canvas edge is local by default. Promoting it to a knowledge relation requires a type and explanation. Existing knowledge relations may also be referenced on a canvas. Deleting a canvas edge removes only that canvas presentation; deleting the knowledge relation requires a separate command.

When a knowledge relation is deleted, its canvas edges become local edges with a visible status. Title changes propagate to all references; layouts on different canvases remain independent.

The graph displays only saved knowledge relations. It does not automatically treat every canvas line as a fact. Automatic layout must not overwrite manual positions on other canvases.

## API and persistence strategy

- `/api/objects`: CRUD, filtering, and pagination. PATCH includes a `version`; stale versions return 409 to prevent overwriting changes from another tab.
- `/api/relations`: creation, type/description updates, deletion, and evidence management. `/api/graph?center=&depth=` returns objects and relations.
- `/api/canvases`: CRUD. `PUT /:id/document` atomically saves items, edges, and viewport after checking the version.
- `/api/sessions`: logs and linked objects. `/api/runs`: experiment runs and artifacts.
- `/api/attachments`: upload, read, and reference attachments. Reject path traversal; the browser uses attachment IDs only.
- `/api/export` and `/api/import`: a versioned manifest, data from all tables, attachments, and an optional external artifact manifest.
- `/api/health`: report service and database connectivity separately.

Debounce saves and warn about unsaved changes when navigating away. IndexedDB is only a cache for unsubmitted drafts; the server database is authoritative. Store object revision snapshots, and use canvas history snapshots for key undo and restore operations.

The first search version covers titles, bodies, tags, and types. Use substring matching for Chinese initially; do not assume PostgreSQL's built-in English full-text tokenization handles Chinese correctly. Evaluate `pg_trgm` or a Chinese search solution as the collection grows.

## Implementation sequence and acceptance

1. Environment integration: confirm the database host, port, database name, and application account; verify authentication and create a separate database. The service was running on recheck; credentials are entered locally.
2. Project skeleton: start both services, add health checks and database migrations, and verify separate ports and environments.
3. End-to-end workflow: create objects, body content, relations, and a local graph, with persistence and failure feedback.
4. Graph and canvas: edit connections, reference the same object, save multiple canvases, group items, and undo.
5. Timeline and experiments: link logs, runs, metrics, artifacts, and next steps.
6. Export and restore: verify data and attachment integrity in a clean test database.
7. Begin the first robotics learning experiments after passing the acceptance checks below.

Acceptance scenario: a UnifoLM-WMA-0 model object → official repository → world model concept → a question asking which configuration can run on a 4090 → a research log entry. Include Chinese and English content and equations, with at least two canvases referencing the same object.

Required checks: relation types can be changed; renaming preserves connections; layouts survive refresh and remain independent; local edges do not enter the global graph; deletions can be restored; records survive service restarts; export/restore preserves IDs, bodies, relations, evidence, layouts, logs, and attachments; edits in multiple tabs do not silently overwrite one another.

Use targeted tests for database constraints, atomic saves, version conflicts, and backup/restore. Verify changes limited to visual layout in the browser.

## Learning cadence

The first tasks follow completion criteria rather than a fixed calendar: understand a robot trajectory → explain observation and action units → run a small imitation learning task → save failure cases and reproducible configurations.

Each stage has completion criteria. The next task follows from gaps in understanding and experiment results. Progress does not depend on fixed weekly hours.

## References

- [React Flow save and restore](https://reactflow.dev/examples/interaction/save-and-restore)
- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)
- [Vite](https://vite.dev/guide/)
- [FastAPI](https://fastapi.tiangolo.com/)
