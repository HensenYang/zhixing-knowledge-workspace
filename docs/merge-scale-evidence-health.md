# Scale / evidence-health merge verification

Verified on 2026-10-23. Merged `origin/feature/p2-p1-scale-evidence-health` into local `main`.

## Resolution

- Preserved main's source imports, Zotero and LLM integration, portable learning-path artifacts, collaboration/authentication, workspace row-level security and bilingual UI.
- Integrated paginated lists and totals, bounded whole-graph rendering, batched queries, connection pooling, asynchronous restore jobs and evidence-health checks.
- Added V009: workspace ownership, creator metadata and forced row-level security for background jobs, plus workspace-first active-list indexes. Legacy jobs without a trustworthy owner stay hidden; they are not assigned to an arbitrary user.
- Pooled transactions retain request-local user/workspace settings. Worker threads copy the request context. Authentication transactions use the same pool without inheriting request scope.
- Preserved workspace filtering of learning paths in paginated trash. Added a connection-slot cleanup regression for failed transaction preparation.
- Localized the new UI and structured evidence messages; original note titles and source text are preserved when switching languages.
- Updated inherited browser scenarios to authenticate both API and browser contexts. CI uses a non-superuser database role so RLS cannot be bypassed, and the scratch e2e runner marks its disposable environment explicitly. The Windows-only pywin32 lock entry has a platform marker for Linux CI.

## Validation

All database validation used fresh disposable PostgreSQL clusters and an unprivileged test role. The personal `.env` and database were not used by the regression runner.

- Full integration run: **175 backend tests and all 40 browser tests passed**, plus localization, frontend unit tests, production build and migrations.
- Final migration/pool regression run: **176 backend tests and 12 focused browser tests passed**, including evidence-health and bilingual workflows. Frontend unit tests, build and V001-V009 fresh migrations passed again.
- `python -m pyflakes backend scripts` and `git diff --check` passed.
- No production database migration or service restart is included in this merge. Existing installations must apply the latest migrations before starting the updated services.

Private machine logs and reports remain under ignored `storage/full-tests/`. GitHub Actions independently validates the pushed merge; local results above do not claim that a remote workflow has already completed.
