# Learning path artifacts / 学习路径文件分享

## Create and share / 创建与分享

1. Open **Research Learning Paths / 研究学习路径**, create or edit a path, and add knowledge objects as steps.
2. Fill in the objective, guidance, and completion criteria. The artifact graph includes the selected objects and their existing mutual relationships and evidence.
3. Click **Save and preview artifact / 保存并预览 Artifact**. This saves the path first and then creates a read-only snapshot. Regenerate the preview after editing.
4. Download an **HTML artifact** for offline browsing or a **JSON package** for exchange. Both formats can be imported into the website.

HTML contains its own viewer, styles, graph data, and Chinese/English presentation labels. It requires no server, CDN, model API, or login. Select graph nodes to inspect summaries, source links, bibliographic/model metadata, and relationship evidence. The numbered steps describe learning order; graph arrows describe knowledge relationships.

HTML 文件内置图谱、查看器及中英文标签，可直接离线打开。点击图谱节点查看摘要、来源、版本等元信息和关系证据。用户填写的正文、标题及步骤保持原文。

The full text of selected knowledge objects is optional and disabled by default. If included, it is available as original Markdown in the inspector. The standalone viewer renders simple headings, paragraphs, and fenced code for guidance; it does not render LaTeX or reproduce the full website Markdown renderer. Attachments, PDF/image binaries, experiments, logs, comments, accounts, workspace membership, revisions, import-provider configuration, and model keys are not packaged. External sources can be opened explicitly; no remote images or resources are fetched by the offline viewer.

正文默认不包含，可在导出前勾选；包含时以原始 Markdown 展示。附件文件不打包，正文中的本机附件链接在接收方不保证可用。分享前应检查预览中的文本、来源和证据是否适合分享。

## Import and browse / 导入与浏览

Open **Import a learning path file / 导入学习路径文件** from the path list, editor, or public share page. The direct route is `/artifacts`.

- Choose a UTF-8 `.html` or `.json` file up to 8 MB. The browser validates and previews it locally. Uploaded HTML is never mounted or executed: only the embedded JSON snapshot is extracted.
- Anonymous visitors and read-only members can browse and download a validated artifact without saving it.
- Owners and editors can explicitly choose **Save a copy to this workspace / 保存副本到当前工作区**. The backend revalidates the file and creates the path, objects, relationships, and evidence in one transaction.
- All imported entity IDs are newly generated. Existing records are never overwritten or merged by ID or title. Local `/knowledge/<id>` references to included objects are remapped to the new copies. Imported paths start as unpublished drafts.
- A failed import is rolled back. Reimporting a file creates another independent copy.

预览不会写入数据库。只有明确点击保存后，才会在当前工作区创建新副本；需要所有者或编辑者权限。导入不会沿用原有分享令牌，也不会自动发布。

## Links versus files / 链接与文件

Existing published links show the current published path and a graph of the available linked objects. Public snapshots contain summaries, sources, safe bibliographic/model metadata, and evidence; they do not include full note bodies. Stopping sharing revokes the link. A file already downloaded is an independent snapshot and cannot be revoked or updated remotely.

链接分享与文件分享同时保留。停止分享仅使链接失效，无法撤回已经下载或转发的 HTML / JSON 文件。

## Format and API

The versioned format is `zhixing-learning-path`, version `1`. It includes `created_at`, `includes_body`, `path`, `objects`, and `relations`. IDs are UUIDs. Limits are 100 steps, 100 objects, 1,000 relationships, and 100 evidence records per relationship. Both the browser and backend check references, duplicate IDs, allowed fields, safe source URLs, metadata fields, and size limits. HTML adds viewer code and labels, so a near-limit JSON package may need less content to fit into an HTML artifact of the same maximum size.

- `GET /api/learning-paths/{id}/artifact?include_body=false`: authenticated workspace snapshot. Object membership is limited to the path and the active workspace.
- `GET /api/shared/learning-paths/{token}`: current public path plus an `artifact` snapshot; unpublished, deleted, or revoked paths are unavailable.
- `POST /api/learning-paths/import`: multipart `file`, accepting JSON or HTML; requires owner/editor access. Returns the newly created unpublished path.

This feature reuses the existing learning path, object, relationship, evidence, and tag tables. No new database migration is required beyond the current collaboration schema.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_path_artifacts.py -q
Set-Location frontend_Web
npm run check:i18n
npm run test:i18n
npm run test:artifacts
npm run build
npx playwright test tests/path-artifacts.spec.js tests/learning-paths.spec.js tests/i18n-language.spec.js
```

The unit and mocked browser tests do not require database credentials or a model key. Database round-trip and workspace-isolation tests in `backend/tests/test_workspace.py` require an explicit `TEST_DATABASE_URL` pointing to an isolated test database. Never run them against a personal production database.
