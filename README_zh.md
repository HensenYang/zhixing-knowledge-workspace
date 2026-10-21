# 知行 · Knowledge in Motion

[English](README.md) | **简体中文**

A relationship-driven knowledge workspace for scientific communication and education.

将论文、代码、数据集、概念与实验连接成可探索、可追溯的学习路径。具身智能是当前案例，框架也可用于其他科学领域的研究交流与教学。

## 功能

- Markdown与公式笔记、来源和标签、版本冲突检查与浏览器草稿。
- arXiv、DOI、GitHub、PDF、本地 Zotero 与可选 MCP 资料导入；确认后入库，避免覆盖现有内容。
- 带类型及证据的知识关系、全局图谱和可编辑画布。
- 可保存、排序和发布的研究学习路径，包含学习目标、讲解提示与逐步完成条件。
- 沿关系阅读：前置基座、方法应用、证据与横向比较；局部图跟随阅读位置并突出访问路径。
- 学习日志、待运行及已运行实验、附件、回收站、ZIP备份恢复。
- 单篇知识资料可导出为Markdown、Word或PDF，包含来源、关系与证据。

## 界面语言

在顶栏的语言选择器中切换中文或英文。偏好保存在浏览器，并同步至其他已打开的标签页。界面文案、系统提示、图谱控件和日期格式会随语言切换；笔记正文、研究资料和模型回复保留原文。

后续新增界面文案须同时提供中英文翻译，参见[国际化开发说明](docs/i18n.md)。

## 技术结构

React 18 / Vite 5 / Tailwind CSS，Cytoscape图谱与React Flow画布；Python / FastAPI；PostgreSQL。
前端地址 http://127.0.0.1:5174/ ，后端端口8001。默认仅监听本机，当前为个人使用版本；每位协作者独立运行，不自动同步修改。

## 本机启动（Windows）

准备Python 3.12、Node.js和npm（Vite 5要求Node 18或 >=20）、已启动的PostgreSQL。克隆仓库后在项目根目录的PowerShell中执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\setup_database.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

数据库设置脚本会在本机询问管理员凭据，创建独立数据库与应用账号，并将随机应用密码写入本机 `.env`。已有同名数据库、角色或 `.env` 时会停止并保留原配置，避免覆盖。

停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

## 本地 Zotero 文献库（可选）

资料导入页通过 stdio 对接 [kujenga/zotero-mcp](https://github.com/kujenga/zotero-mcp)，支持搜索本机文献库、读取条目元数据与已索引全文、编辑预览，并在确认后导入。此流程不修改 Zotero，也不调用大模型。

1. 打开 Zotero，在高级设置中启用“允许此计算机上的其他应用程序与 Zotero 通信”。需要全文时，请先下载附件并等待 Zotero 完成全文索引。
2. 如未安装 `uv`，请先安装；然后准备兼容版本：`uvx zotero-mcp@0.3.1 --help`。
3. 在项目已有 `.env` 中追加以下配置，保留数据库和模型配置：

   ```dotenv
   ZOTERO_MCP_ENABLED=true
   ZOTERO_MCP_COMMAND=uvx
   ZOTERO_MCP_ARGS=["zotero-mcp@0.3.1"]
   ```

4. 重启后端。使用项目内置 PostgreSQL 的本机部署，可先运行 `scripts/stop.ps1` 停止应用，再运行 `storage/local/start.ps1`；正常启动会自动应用待执行的数据库迁移。
5. 进入“资料导入 → 来源类型 → Zotero（本地文献库）”，填写搜索词，选择搜索范围和可选标签，点击“搜索 Zotero 文献”。在结果中选择“读取并预览”，检查并编辑标题、摘要、标签、元数据和正文，最后点击“确认并创建知识对象”。

全文和图片附件分别控制；仅导入元数据时，请同时取消勾选“预览时包含已索引全文（可用时）”和“附带原始 PDF 和提取图片”。附件缺失、未索引或读取失败时，预览会显示警告并保留元数据。检索上限限制的是归并前的匹配数；需要更多结果时可提高上限或缩小搜索范围。多个词请用空格分隔，Zotero 会把连字符解释为“或”。

后端直接启动本机配置的程序，仅调用三个只读 Zotero 工具。启动命令只能由本机配置提供，浏览器不能传入命令。子进程固定使用本地文献库模式，不转发数据库密码或 LLM 密钥。如果后端 PATH 中找不到 `uvx`，请将 `ZOTERO_MCP_COMMAND` 改为其绝对路径。工作台不会自动读取其他客户端的 MCP 配置。

确认导入后会保留 Zotero 条目 Key、定位 URI、引用 Key、作者、日期、DOI、原始元数据文本和可用全文，勾选图片附件选项时，会在确认后复制本地可用的原始 PDF 和提取图片；无法读取原始 PDF 时会提示，并保留文本预览。已有有效导入会提示打开资料或明确选择另存笔记；旧资料在回收站时允许重新导入，保留回收站中的原记录。来源沿用既有 `mcp` 标识，并为 Zotero 条目设置独立前缀；除资料导入功能已有迁移外，无需额外迁移。

搜索与预览接口分别为 `POST /api/source-imports/zotero/search`（`query`、`qmode`、可选 `tag` 与 `limit`）和 `POST /api/source-imports/zotero/preview`（`item_key`、`include_fulltext`、`include_media`）。数据库写入仍由原有确认接口执行。详见[资料导入导出说明](docs/import-export.md)。

## 导入图片与 HTML 阅读

- **本地 PDF**：提取嵌入的位图，并将含矢量图形的页面保存为整页图像预览。图片引用放在对应页的正文之后，不自动识别独立图表边界或图注，也不执行 OCR；原始 PDF 一并保留。
- **Zotero**：在“读取并预览”前勾选“附带原始 PDF 和提取图片”。后端通过 Zotero 固定的本机 API 获取存储附件或链接附件的 PDF，浏览器不能指定文件路径。原 PDF 不可用时仍可使用已索引文本。
- **预览与保存**：先检查图片缩略图和正文阅读预览，按需编辑 Markdown，再确认导入。确认前的文件只存放在临时预览区，不创建知识对象。确认时笔记、来源记录、原 PDF、图片附件和永久正文引用一起保存；数据库保存失败时清理已复制文件，并保留预览供重试。已保存的图片与 PDF 会包含在 ZIP 备份中。
- **GitHub**：Markdown 与 HTML 图片路径依据 README 所在目录和导入时的 commit 解析；没有 commit 时使用分支。相对文档链接会指向对应 GitHub 页面，GitHub `blob` 图片地址会转换为原始内容地址。这些图片仍为远程资源，显示需要网络，不会自动下载为本地附件。已有笔记在阅读时生效，不改写已保存正文。
- **HTML 阅读**：支持 Markdown 中的 HTML 标题、表格、图片、居中区块、折叠详情和章节锚点。HTML 经解析和清理后渲染，移除脚本、事件属性、iframe 和任意内联样式；同时保留公式、代码块与普通 Markdown。切换界面语言不会改写研究内容。

PDF 大小上限仍为 32 MB。图片提取最多处理 200 页、80 张去重图片或整页预览，临时资源合计不超过 72 MB；图片最长边最高为 1,800 像素。达到限制时会显示提示，完整来源保留在原 PDF 中。文字预览沿用现有字符上限，图片引用另外追加。临时预览链接两小时后失效，若确认时提示过期，请重新提取；确认后的图片链接保留到附件被删除为止。

## LLM / API Key（可选）

原始工作台没有接入 LLM；研究案例中的宇树模型是学习对象，不是驱动工作台的模型。
现在提供可选的 OpenAI 兼容 Chat Completions 文本接口，实际模型由你配置的服务商与模型 ID 决定。
没有配置时，原有笔记、图谱、画布等功能照常使用。

在已有本机 `.env` 中追加以下配置（勿覆盖数据库配置）：

```dotenv
LLM_API_KEY=你的服务商密钥
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=你的账号可用的模型ID
LLM_TIMEOUT_SECONDS=60
LLM_MAX_OUTPUT_TOKENS=1024
LLM_TOKEN_PARAMETER=max_completion_tokens
```

API 地址需填写服务商提供的基础地址，例如包含 `/v1`，不要追加 `/chat/completions`。
远程服务必须使用 HTTPS；本机 localhost、127.0.0.1、::1 可以使用 HTTP。
部分兼容服务使用 `max_tokens`，此时将 `LLM_TOKEN_PARAMETER` 改为 `max_tokens`。
仅支持该协议的文本接口，不能直接填写 Anthropic、Gemini 原生接口或 Azure 专有接口。
超时范围为 1–120 秒，输出上限为 1–8192 tokens；上限可能包含模型的推理 tokens，需结合模型调整。

修改后重启后端，在“环境与备份 → LLM 接入”查看配置，并点击“测试模型连接”。
配置完整不代表认证通过；测试会发送固定短消息并可能产生 API 费用，不发送知识库内容。
密钥仅由后端读取，不返回前端、不保存到数据库、不包含在工作台备份中；不要使用 `VITE_` 变量或提交密钥。
每位协作者独立配置本机 `.env`。现有服务仍只适合本机个人访问；远程共享需要先增加身份验证和访问控制。

供后续功能复用的接口（均不依赖数据库）：

- `GET /api/llm/status`：查看配置状态，不调用模型、不返回密钥。
- `POST /api/llm/test`：发送固定短消息验证模型调用。
- `POST /api/llm/chat`：发送 `{"messages":[{"role":"user","content":"用一句话解释知识图谱"}]}`，返回 `model`、`content`、`usage` 与 `finish_reason`。

聊天接口是后续解释、问答和教学功能的基础；不会自动检索或发送知识库，也不会自动提供来源引用。
若 `finish_reason` 为 `length`，表示生成触及上限，内容可能不完整。外部服务只接收显式提交的消息。

协议参考：[Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) · [认证与后端密钥管理](https://developers.openai.com/api/reference/overview)。

无需真实密钥或数据库即可验证接入层：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_llm.py -q
```

## 使用 LLM 解析导入文献

1. 将本地 PDF 或 Zotero 文献读取到导入预览。需要分析文献文本时请包含全文；只有元数据时，只能依据元数据和摘要分析。
2. 点击“使用 LLM 解析”。当前标题、摘要和 Markdown 正文会发送给已配置的服务商，可能产生 API 费用。图片文件和原始 PDF 不发送给模型，不执行 OCR，也不理解图像内容。
3. 模型判断文献正文的主要语言，用该语言生成摘要、方法、主要结论和局限。界面语言不决定生成语言，切换界面语言不会重译结果；多语言文献使用其主要正文语言。
4. 检查并编辑结果。解析内容添加在正文开头，后面保留原文及图片引用。“移除解析并恢复解析前草稿”会恢复解析前的正文、摘要和元数据。请求失败或模型结果无效、被截断时，草稿保持原样。
5. 确认后才保存。已有有效导入时可打开原资料，或勾选“另存为独立笔记”；独立笔记保留来源信息，不覆盖原资料。旧资料在回收站时，重新导入会创建新对象，旧资料仍留在回收站。

长文最多选取开头、中间和结尾合计 48,000 个正文字符进行分析，界面与模型提示都会说明节选范围；完整输入草稿仍保留在保存正文中。解析元数据记录模型、时间、检测语言、输入哈希、输入与分析字符数、令牌用量。生成内容属于辅助阅读结果，应对照原文核实。

`POST /api/source-imports/analyze` 接收 `title`、`summary`、`body_md`，返回 `language`、`summary`、`analysis_md` 和 `provenance`，不会写入知识对象。`POST /api/source-imports/commit` 支持可选 `save_as_note`（默认 `false`）；有效来源重复时返回 HTTP 409，`detail.message` 为提示、`detail.existing_import` 为已有资料定位信息。确认保存仍以事务处理附件，无需新数据库迁移。

## 学习案例

[宇树模型研究资料](research/unitree-group-01/README.md)包含模型拆解、上游论文、来源链接及按完成条件推进的任务。该组资料核对日期为2026-10-01，未代表已完成GPU复现或验证教学效果。

新数据库可按需运行以下脚本录入学习案例，勿将阅读记录误当作已掌握：

```powershell
.\.venv\Scripts\python.exe research/unitree-group-01/import_workspace.py
.\.venv\Scripts\python.exe research/unitree-group-01/finalize_workspace.py
```

需要先保持本机服务运行。也可在“环境与备份”向空数据库导入自己持有的备份，ID冲突时不会覆盖现有内容。

## 可携带的学习 Artifact

已保存的学习路径可展示交互图谱、目标、步骤、来源和关系证据。支持下载可离线打开的 HTML Artifact 或 JSON 文件包，两种文件都可在 `/artifacts` 中预览，并明确保存为当前工作区的独立副本。

[Artifact 分享与导入说明](docs/learning-path-artifacts.md)

## 科学交流与教育

项目侧重来源追溯、概念联系和可回看的学习路径。Hackathon目标是在现有原型上演示研究讲解及跨学科教学场景，评估证据追溯、解释清晰度与导航体验。

[Motivation / Problem definition / Hackathon target](output/pdf/project-introduction.md)

## 数据与隐私

仓库只保存框架源码、教学研究案例和项目介绍。数据库密码、`.env`、运行数据库、附件、个人学习日志、备份ZIP、运行日志、浏览器草稿和阅读历史均留在本机，不提交Git。

- PostgreSQL：笔记、关系、画布、日志、实验配置。
- `storage/`：本机附件、备份、运行日志。
- IndexedDB：未提交草稿；sessionStorage：当前标签页的阅读路径。
- `.env.example`：仅配置格式示例，不含真实凭据。

分享仓库或邀请协作者时请保持GitHub仓库为Private。多人同时访问的远程部署需另行设计身份验证、权限与同步。

## 开发与验证

```powershell
Set-Location frontend_Web
npm run build
npx playwright test tests/reading-navigation.spec.js
npx playwright test tests/llm-settings.spec.js
npx playwright test tests/i18n-language.spec.js
```

阅读导航测试使用模拟接口。其他后端／浏览器验收可能写入测试数据，必须连接隔离测试数据库；参见测试代码中的 `TEST_DATABASE_URL` 配置，勿对个人正式数据库运行。

[框架设计](docs/phase-1-design.md) · [分享包说明](docs/share-guide.md)

第三方代码、模型和数据仍受原始许可约束。案例中的官方源码快照属于本机研究缓存，不提交仓库；固定版本及原始出处见资料清单和笔记。

资料导入与单篇文档导出：[使用说明](docs/import-export.md)。可保存、排序和分享的研究学习路径：[使用说明](docs/learning-paths.md)。
