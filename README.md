# Zhixing · Knowledge in Motion

**English** | [简体中文](README_zh.md)

A relationship-driven knowledge workspace for scientific communication and education.

Connect papers, code, datasets, concepts, and experiments into learning paths that can be explored and traced back to their sources. Embodied AI is the current case study; the framework can also support research communication and teaching in other scientific fields.

## Features

- Markdown notes with mathematical notation, sources, tags, version conflict checks, and browser drafts.
- Import arXiv, DOI, GitHub, PDF, and optional MCP sources, with a review before saving.
- Typed knowledge relationships with supporting evidence, a global graph, and editable canvases.
- Save, reorder, and publish research learning paths with goals, guidance, and completion criteria.
- Relationship-based reading: explore prerequisites, applications, evidence, and comparisons. The local graph follows the current note and highlights the reading trail.
- Learning logs, planned and completed experiment records, attachments, a recycle bin, and ZIP backup and restore.
- Export individual knowledge materials as Markdown, Word, or PDF with sources, relationships, and evidence.

## Interface language

Use the language selector in the header to switch between Chinese and English. The preference is saved in your browser and synchronized across open tabs. Interface labels, system messages, graph controls, and dates follow the selected language. Your notes, research materials, and model responses keep their original content.

New interface text must include both translations. See the [localization guide](docs/i18n.md).

## Architecture

React 18 / Vite 5 / Tailwind CSS, Cytoscape for graphs, and React Flow for canvases; Python / FastAPI; PostgreSQL.

The frontend runs at http://127.0.0.1:5174/ and the backend uses port 8001. Services bind to the local machine by default. This is currently a personal workspace: each collaborator runs an independent instance, and changes are not synchronized automatically.

## Local setup (Windows)

Install Python 3.12, Node.js and npm (Vite 5 requires Node 18 or >=20), and make sure PostgreSQL is running. After cloning the repository, run these commands in PowerShell from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\setup_database.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

The database setup script prompts locally for administrator credentials, creates a dedicated database and application role, and writes a randomly generated application password to the local `.env` file. If a database, role, or `.env` with the same name already exists, setup stops and preserves the existing configuration.

To stop the services:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

## LLM / API key (optional)

The original workspace did not use an LLM. The Unitree models in the research collection are study subjects, not models powering the application.

An optional text interface now supports OpenAI-compatible Chat Completions APIs. The actual model is determined by your configured provider and model ID. Notes, graphs, canvases, and other existing features work without LLM configuration.

Append the following settings to your existing local `.env` file, keeping the database configuration:

```dotenv
LLM_API_KEY=your-provider-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your-available-model-id
LLM_TIMEOUT_SECONDS=60
LLM_MAX_OUTPUT_TOKENS=1024
LLM_TOKEN_PARAMETER=max_completion_tokens
```

Use the base URL supplied by your provider, including `/v1` if required. Do not append `/chat/completions`.

Remote services must use HTTPS. Local services at `localhost`, `127.0.0.1`, or `::1` may use HTTP. Some compatible providers require `max_tokens`; in that case, set `LLM_TOKEN_PARAMETER=max_tokens`.

Only text endpoints using this protocol are supported. Native Anthropic or Gemini endpoints and Azure-specific endpoints cannot be used directly. The timeout must be 1–120 seconds, and the output limit must be 1–8192 tokens. The limit may include reasoning tokens, so adjust it for your model.

Restart the backend after changing configuration. Open **Environment & Backup → LLM Access** (currently labeled “环境与备份 → LLM 接入” in the UI), then click **Test Model Connection** (“测试模型连接”). Complete configuration does not confirm successful authentication. The test sends a fixed short message and may incur API charges; it does not send knowledge base content.

The API key is read only by the backend. It is not returned to the frontend, stored in the database, or included in workspace backups. Do not use `VITE_` variables for secrets or commit keys to Git. Each collaborator configures their own local `.env`. The application remains intended for personal local access; remote sharing requires authentication and access controls first.

The following endpoints are available for future features and do not require a database:

- `GET /api/llm/status`: inspect configuration without calling the model or returning the key.
- `POST /api/llm/test`: verify model access with a fixed short message.
- `POST /api/llm/chat`: send `{"messages":[{"role":"user","content":"Explain knowledge graphs in one sentence."}]}` and receive `model`, `content`, `usage`, and `finish_reason`.

The chat endpoint provides a foundation for explanations, question answering, and teaching features. It does not automatically retrieve or send knowledge base content or provide source citations. A `finish_reason` of `length` means generation reached the output limit and may be incomplete. Only explicitly submitted messages are sent to the external service.

Protocol references: [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) · [Authentication and server-side key management](https://developers.openai.com/api/reference/overview).

Test the integration without a real API key or database:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_llm.py -q
```

## Learning case study

The [Unitree model research collection](research/unitree-group-01/README.md) contains model breakdowns, upstream papers, source links, and tasks organized by completion criteria. Sources were checked on October 1, 2026. This collection does not establish that GPU reproduction or educational effectiveness has been validated.

For a new database, you can optionally import the case study with these scripts. Reading records should not be treated as evidence of mastery:

```powershell
.\.venv\Scripts\python.exe research/unitree-group-01/import_workspace.py
.\.venv\Scripts\python.exe research/unitree-group-01/finalize_workspace.py
```

Keep the local services running while importing. You can also restore a backup you own into an empty database through **Environment & Backup** (“环境与备份”). Existing records are not overwritten when IDs conflict.

## Scientific communication and education

The project focuses on source traceability, conceptual connections, and revisitable learning paths. The hackathon goal is to demonstrate research explanations and teaching scenarios across disciplines using the existing prototype, evaluating evidence traceability, explanation clarity, and navigation.

[Motivation / Problem definition / Hackathon target](output/pdf/project-introduction.md)

## Data and privacy

The repository contains framework source code, educational research examples, and project introductions. Database passwords, `.env`, the live database, attachments, personal learning logs, backup ZIPs, runtime logs, browser drafts, and reading history remain local and are not committed to Git.

- PostgreSQL: notes, relationships, canvases, logs, and experiment configurations.
- `storage/`: local attachments, backups, and runtime logs.
- IndexedDB: unsubmitted drafts; sessionStorage: the current tab's reading trail.
- `.env.example`: configuration examples only, with no real credentials.

Keep the GitHub repository private when sharing it or inviting collaborators. A remote deployment serving multiple users requires a separate design for authentication, permissions, and synchronization.

## Development and verification

```powershell
Set-Location frontend_Web
npm run check:i18n
npm run test:i18n
npm run build
npx playwright test tests/reading-navigation.spec.js
npx playwright test tests/llm-settings.spec.js
npx playwright test tests/i18n-language.spec.js
```

The reading navigation tests use mocked APIs. Other backend and browser acceptance tests may write test data and must use an isolated test database. See the `TEST_DATABASE_URL` configuration in the tests; do not run them against your personal production database.

[Framework design](docs/phase-1-design.md) · [Sharing guide](docs/share-guide.md)

Third-party code, models, and datasets remain subject to their original licenses. Official source snapshots used in the case study are local research caches and are not committed to the repository. See the source manifests and notes for pinned versions and original sources.

Source import and document export: [guide](docs/import-export.md). Saved and shareable research learning paths: [guide](docs/learning-paths.md).
