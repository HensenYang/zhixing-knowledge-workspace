# Full Regression Test Report

[Chinese version](full-test-report-zh.md)

Date: 2026-10-22

## Results

The final full regression passed.

| Check | Result |
| --- | --- |
| Backend unit tests and real database integration | 116 passed, 0 failed, 0 skipped |
| Frontend unit tests | 11 passed, 0 failed |
| Chrome browser scenarios | 32 passed, 0 failed |
| `npm run check:i18n` | Passed: 906 paired messages |
| `npm run test:i18n` / `npm run test:artifacts` | Passed: 5 / 3 tests; included in the 11 frontend unit cases above |
| `npm run build` | Passed |
| `git diff --check` / Python compile checks | Passed |

Run evidence:

- [Stage results](../storage/full-tests/20261022-050225/summary.json)
- [Backend JUnit XML](../storage/full-tests/20261022-050225/backend.xml)
- [Browser scenario results](../storage/full-tests/20261022-050225/browser-fallback.json)
- [Note screenshot](../storage/screenshots/note.png)
- [Canvas screenshot](../storage/screenshots/canvas.png)

Raw logs, screenshots, and disposable database files are local test artifacts ignored by Git. Test sources and this report are kept in the repository.

## Environment

The final run used a fresh PostgreSQL cluster, a non-superuser database role that preserves row-level security checks, isolated file storage, temporary API/frontend ports, and real Chrome. It did not read the personal `.env`, write to the everyday database or Zotero library, or make paid model requests.

## Coverage

| Feature | Checks |
| --- | --- |
| Source import | Real PDF extraction; preview without database writes; confirmation after editing the title, summary, and tags; downloading the original PDF attachment; images and body references; duplicate imports; reimport after deletion; independent imports of the same source in different workspaces |
| Knowledge notes | Creation through the UI, autosave, draft preservation when switching languages, restoration after refresh, search, version history, conflict preservation, equation/code rendering, and HTML sanitization |
| Learning paths | Creation through the UI, adding knowledge objects, editing prompts/completion criteria/estimated duration, reordering steps, persistence after refresh, publishing, anonymous read-only browsing, and stopping sharing |
| Artifacts | HTML/JSON export, offline HTML browsing, key information and relation evidence, body visibility toggle, file import preview, saving an independent copy, ID remapping, prevention of malicious HTML execution, and read-only role restrictions |
| Freeform canvas | Connecting cards, editing edges, promoting edges to formal knowledge relations, dragging positions, undo, grouping, restoration after refresh, renaming, version conflicts, and transaction atomicity |
| Graph and records | Node/relation editing, deletion and restoration, evidence preservation, archiving, confirmation before permanent deletion from trash, learning logs, experiment runs, and backup/restore |
| Collaboration and UI | Authentication restrictions, workspace isolation, member permissions, comments and reviews, desktop/narrow-screen navigation, Chinese/English switching and synchronization across tabs, and uncaught browser exceptions |

PDF import, notes, learning paths, canvases, record management, and persistence were tested against the real API and database. Browser adapter and error scenarios also used mocked APIs to exercise cases deterministically.

## Fixes in this run

Source import confirmation still used the old `ON CONFLICT (source_type, source_key)` target after the multi-workspace migration had changed the unique constraint to `(workspace_id, source_type, source_key)`. This caused imports to return 503. The upsert now matches the workspace-scoped constraint. Regression checks verify duplicate-source conflicts within one workspace and independent imports across workspaces without overwriting one another. No new migration was required.

Older LLM, source analysis, and Zotero handler unit tests, along with some browser mocks, had not yet been adapted to authentication. Handler contract tests now use isolated FastAPI applications and route entry points. Database integration tests verify the real application's authentication and permissions, with the production authentication middleware kept enabled.

## Reproduction

Run from the repository root using the existing virtual environment and installed PostgreSQL and Node programs. The runner always initializes a disposable PostgreSQL cluster and never accepts a personal database URL.

```powershell
.\.venv\Scripts\python.exe scripts/verify_full.py --browser-fallback
```

If programs are installed elsewhere, pass `--postgres-bin "C:\path\pgsql\bin" --node "C:\path\node.exe"`. By default, the runner uses programs in the project's local `storage/runtime` directory. Chrome must be installed.

Omit `--browser-fallback` to use the standard Playwright CLI. CLI worker startup stalled on the local machine, so this run used the single-process fallback runner. It executes the same spec functions, Playwright browser actions, and `expect` assertions, creating a fresh browser context for each scenario. The fallback supports only the `page/context/browser` fixtures and `beforeEach` hooks currently used by the repository, with a 90-second limit per scenario.

Logs and results are saved under `storage/full-tests/<timestamp>/`, including backend JUnit XML, browser scenario JSON, build logs, and failure screenshots. Temporary services stop automatically when the run ends. Use `--spec full-workflow.spec.js` to restrict browser scenarios; backend and build checks still run in full.

## Scope and limitations

External LLM services, real Zotero connections, and online arXiv/DOI/GitHub availability were tested with deterministic mocks and adapter contracts. These results do not certify live availability with a particular network or API key.

PDF tests used automatically generated materials and did not cover every scanned document, font, or complex layout. Narrow-screen checks covered navigation and main pages, rather than visual compatibility on every device. No load testing was performed.
