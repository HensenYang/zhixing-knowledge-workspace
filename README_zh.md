# 知行 · Knowledge in Motion

[English](README.md) | **简体中文**

A relationship-driven knowledge workspace for scientific communication and education.

将论文、代码、数据集、概念与实验连接成可探索、可追溯的学习路径。具身智能是当前案例，框架也可用于其他科学领域的研究交流与教学。

## 功能

- Markdown与公式笔记、来源和标签、版本冲突检查与浏览器草稿。
- arXiv、DOI、GitHub、PDF与可选MCP资料导入；确认后入库，避免覆盖现有内容。
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

## 学习案例

[宇树模型研究资料](research/unitree-group-01/README.md)包含模型拆解、上游论文、来源链接及按完成条件推进的任务。该组资料核对日期为2026-10-01，未代表已完成GPU复现或验证教学效果。

新数据库可按需运行以下脚本录入学习案例，勿将阅读记录误当作已掌握：

```powershell
.\.venv\Scripts\python.exe research/unitree-group-01/import_workspace.py
.\.venv\Scripts\python.exe research/unitree-group-01/finalize_workspace.py
```

需要先保持本机服务运行。也可在“环境与备份”向空数据库导入自己持有的备份，ID冲突时不会覆盖现有内容。

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
