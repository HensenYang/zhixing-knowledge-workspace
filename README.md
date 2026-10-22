# Zhixing · Knowledge in Motion

**English** | [简体中文](README_zh.md)

A relationship-driven knowledge workspace for scientific communication and education.

Connect papers, code, datasets, concepts, and experiments into learning paths that can be explored and traced back to their sources. Embodied AI is the current case study; the framework can also support research communication and teaching in other scientific fields.

## Features

- Markdown notes with mathematical notation, sources, tags, version conflict checks, and browser drafts.
- Import arXiv, DOI, GitHub, PDF, local Zotero, and optional MCP sources, with a review before saving.
- Typed knowledge relationships with supporting evidence, a global graph, and editable canvases.
- Save, reorder, and publish research learning paths with goals, guidance, and completion criteria.
- Relationship-based reading: explore prerequisites, applications, evidence, and comparisons. The local graph follows the current note and highlights the reading trail.
- Learning logs, planned and completed experiment records, attachments, a recycle bin, and ZIP backup and restore.
- Export individual knowledge materials as Markdown, Word, or PDF with sources, relationships, and evidence.
- User login, isolated team workspaces, owner/editor/reviewer/viewer roles, comments, version reviews, and activity history.

## Interface language

Use the language selector in the header to switch between Chinese and English. The preference is saved in your browser and synchronized across open tabs. Interface labels, system messages, graph controls, and dates follow the selected language. Your notes, research materials, and model responses keep their original content.

## Multi-user collaboration

After migration `V005`, content is isolated by workspace. The first registered account takes ownership of existing local data. Workspace owners can add already registered users by email and assign owner, editor, reviewer, or viewer roles. Objects and canvases retain optimistic version checks; a 409 conflict preserves the local IndexedDB draft and offers field-level comparison with the team version.

Backups contain the current workspace's knowledge content, not accounts, passwords, sessions, or membership permissions. Remote deployment must serve the frontend and `/api` from the same HTTPS origin, set `COOKIE_SECURE=true`, keep PostgreSQL off the public network, and use persistent storage for attachments. Local development should keep `COOKIE_SECURE=false`.

New interface text must include both translations. See the [localization guide](docs/i18n.md).

## Architecture

React 18 / Vite 5 / Tailwind CSS, Cytoscape for graphs, and React Flow for canvases; Python / FastAPI; PostgreSQL.

The frontend runs at http://127.0.0.1:5174/ and the backend uses port 8001. Services bind to the local machine by default; a shared deployment can host multiple authenticated, workspace-isolated collaborators.

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

## Local Zotero library (optional)

The import page supports [kujenga/zotero-mcp](https://github.com/kujenga/zotero-mcp) over stdio: search your local library, read an item's metadata and indexed full text, edit the preview, and explicitly confirm the import. It does not modify Zotero or call the LLM.

1. Open Zotero and enable **Allow other applications on this computer to communicate with Zotero** in its advanced settings. Download the relevant attachments and let Zotero index them for full-text access.
2. Install `uv` if needed, then prepare the compatible MCP version: `uvx zotero-mcp@0.3.1 --help`.
3. Add these settings to the project's existing `.env`, preserving your database and model settings:

   ```dotenv
   ZOTERO_MCP_ENABLED=true
   ZOTERO_MCP_COMMAND=uvx
   ZOTERO_MCP_ARGS=["zotero-mcp@0.3.1"]
   ```

4. Restart the backend. If this machine uses the bundled PostgreSQL runtime, stop the app with `scripts/stop.ps1`, then start it with `storage/local/start.ps1`. The normal startup applies pending database migrations.
5. Open **Source Import → Source type → Zotero (local library)**. Enter search terms, choose the search scope and optional tag, and click **Search Zotero library**. Select **Read and preview** on a result, review the editable title, abstract, tags, metadata, and body, then choose **Confirm and create knowledge object**.

Full text and media have separate checkboxes. For metadata-only imports, uncheck both **Include indexed full text in the preview when available** and **Include the original PDF and extracted images**. If an attachment is missing, unindexed, or cannot be read, the preview shows a warning and retains the metadata. Search limits cap matches before grouping by work; increase the limit or refine your query if needed. Separate search words with spaces: Zotero treats a hyphen as OR.

The backend starts the configured executable directly and only calls the three read-only Zotero tools. Commands are configured locally, never supplied by the browser. The child process is forced into local-library mode; database and LLM credentials are not forwarded. If `uvx` is not on the backend's PATH, set `ZOTERO_MCP_COMMAND` to its absolute path. Other clients' MCP settings are not read automatically.

Confirmed imports retain the Zotero item key, selection URI, citation key, authors, date, DOI, original metadata text, and available full text. When media is selected, the locally available original PDF and extracted images are copied on confirmation. If the PDF cannot be read, a warning is shown and text remains available. An active import offers an existing-material link or an explicit separate-note option. A source whose previous material is in the recycle bin can be imported again without changing that trashed material. Zotero uses the existing `mcp` source identifier with a namespaced item key, so this integration needs no additional migration beyond the source-import feature.

Search and preview endpoints: `POST /api/source-imports/zotero/search` (`query`, `qmode`, optional `tag` and `limit`) and `POST /api/source-imports/zotero/preview` (`item_key`, `include_fulltext`, `include_media`). The existing confirmation endpoint performs the database write. See [import/export details](docs/import-export.md).

## Images and HTML in imported material

- **Local PDFs:** preview extracts embedded raster images and preserves pages containing vector graphics as page images. Images appear beneath their source page; this does not identify semantic figure boundaries or captions and does not perform OCR. The original PDF is also included.
- **Zotero:** enable **Include the original PDF and extracted images** before choosing **Read and preview**. The backend asks Zotero's fixed local API for the stored or linked PDF; the browser cannot supply a filesystem path. Indexed text remains usable when the original PDF is unavailable.
- **Review and save:** inspect the image thumbnails and rendered body preview, edit the Markdown, then confirm. Before confirmation, binaries are temporary preview files, not knowledge objects. Confirmation saves the note, source record, original PDF, image attachments, and permanent body references together. Failed database saves clean up copied files and retain the preview for retry. Saved attachments are included in ZIP backups.
- **GitHub:** Markdown and HTML image paths resolve relative to the README directory and imported commit (or branch when no commit is available). Relative document links also resolve to GitHub. GitHub `blob` image links resolve to raw content. These remain remote images and require network access; they are not downloaded as local attachments. Existing notes benefit at read time without changing their stored text.
- **HTML reading:** Markdown may contain headings, tables, images, centered sections, details/summary blocks, and heading anchors. HTML is parsed and sanitized before rendering; scripts, event handlers, iframes, and arbitrary inline styles are removed. Math, code blocks, and normal Markdown remain supported. Changing the interface language does not rewrite research content.

PDFs remain limited to 32 MB. Image extraction processes up to 200 pages, 80 unique images/page previews, and 72 MB of combined preview assets. Images are rendered up to 1,800 pixels on the longest side. A warning explains any skipped assets; the original PDF preserves the complete source. Text previews retain their existing character limit, with image references added separately. Temporary preview URLs expire after two hours; extract again if confirmation reports an expired preview. Confirmed image URLs remain valid until their attachment is deleted.

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

## Analyze an import with an LLM

1. Extract a local PDF or read a Zotero item into the import preview. Include full text for analysis of the supplied document; metadata-only input can only support metadata/abstract-based analysis.
2. Click **Analyze with LLM**. The current title, abstract and Markdown text are sent to your configured provider and may incur charges. Image binaries and the original PDF are not sent; this feature does not perform OCR or visually interpret figures.
3. The model detects the document’s main prose language and writes its summary, methods, findings and limitations in that language. Interface language never selects or retranslates the generated content. Mixed-language documents use their main language.
4. Review and edit the result. The analysis is prepended to the original text; original image references remain intact. **Remove analysis and restore the earlier draft** restores the pre-analysis text, summary and metadata. Errors or truncated/invalid model output leave the draft unchanged.
5. Confirm to save. For an active duplicate source, open the existing material or select **Save as a separate note**; saving a separate note records source provenance without changing the original. Reimporting a trashed source creates a new object and leaves the old one in the recycle bin.

Long inputs use at most 48,000 source characters sampled from the beginning, middle and end. Both the preview and model prompt disclose excerpt coverage; the complete input draft remains in the saved body. Analysis metadata records the model, time, detected language, input hash, input/analysis character counts and token usage. This is a model-generated reading aid: verify its claims against the original.

`POST /api/source-imports/analyze` accepts `title`, `summary` and `body_md`, returning `language`, `summary`, `analysis_md` and `provenance`; it never writes knowledge objects. `POST /api/source-imports/commit` accepts optional `save_as_note` (default `false`). Active duplicates return HTTP 409 with `detail.message` and `detail.existing_import` for an actionable link. Confirmation still saves staged attachments atomically. No new database migration is needed.

## Learning case study

The [Unitree model research collection](research/unitree-group-01/README.md) contains model breakdowns, upstream papers, source links, and tasks organized by completion criteria. Sources were checked on October 1, 2026. This collection does not establish that GPU reproduction or educational effectiveness has been validated.

For a new database, you can optionally import the case study with these scripts. Reading records should not be treated as evidence of mastery:

```powershell
.\.venv\Scripts\python.exe research/unitree-group-01/import_workspace.py
.\.venv\Scripts\python.exe research/unitree-group-01/finalize_workspace.py
```

Keep the local services running while importing. You can also restore a backup you own into an empty database through **Environment & Backup** (“环境与备份”). Existing records are not overwritten when IDs conflict.

## Portable learning artifacts

Saved learning paths can be previewed as interactive knowledge graphs with objectives, ordered steps, sources, and relationship evidence. Download a standalone HTML artifact for offline use or a JSON package for exchange. Both formats can be previewed at `/artifacts` and explicitly imported as independent workspace copies.

[Artifact sharing and import guide](docs/learning-path-artifacts.md)

## Scientific communication and education

The project focuses on source traceability, conceptual connections, and revisitable learning paths. The hackathon goal is to demonstrate research explanations and teaching scenarios across disciplines using the existing prototype, evaluating evidence traceability, explanation clarity, and navigation.

[Motivation / Problem definition / Hackathon target](output/pdf/project-introduction.md)

## Data and privacy

The repository contains framework source code, educational research examples, and project introductions. Database passwords, `.env`, the live database, attachments, personal learning logs, backup ZIPs, runtime logs, browser drafts, and reading history remain local and are not committed to Git.

- PostgreSQL: notes, relationships, canvases, logs, and experiment configurations.
- `storage/`: local attachments, backups, and runtime logs.
- IndexedDB: unsubmitted drafts; sessionStorage: the current tab's reading trail.
- `.env.example`: configuration examples only, with no real credentials.

Keep the GitHub repository private when sharing it or inviting collaborators. The current version detects version conflicts but does not provide character-by-character real-time co-editing.

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
