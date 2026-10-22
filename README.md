# 知行 · Knowledge in Motion

A relationship-driven knowledge workspace for scientific communication and education.

将论文、代码、数据集、概念与实验连接成可探索、可追溯的学习路径。具身智能是当前案例，框架也可用于其他科学领域的研究交流与教学。

## 功能

- Markdown与公式笔记、来源和标签、版本冲突检查与浏览器草稿。
- 带类型及证据的知识关系、全局图谱和可编辑画布。
- 沿关系阅读：前置基座、方法应用、证据与横向比较；局部图跟随阅读位置并突出访问路径。
- 学习日志、待运行及已运行实验、附件、回收站、ZIP备份恢复（大备份在后台恢复并显示进度）。
- **证据健康检查**：找出没有证据的关系、失效链接、过期资料、依赖成环、被支持又被质疑的结论、尚未验证的实验声明和无法复现的运行记录，并给出证据覆盖率。

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

分页、连接池、后台任务和证据健康检查放在 `backend/` 下的独立模块里（`pool.py`、`paging.py`、`jobs.py`、`link_checker.py`、`evidence_health.py`），详见 [工程和规模化与证据健康检查](docs/engineering-and-evidence-health.md)。

所有会写数据的测试都必须指向**隔离的测试数据库**，勿对个人正式数据库运行。先建一个空的测试库，然后：

```powershell
$env:TEST_DATABASE_URL = "postgresql://用户:密码@127.0.0.1:5432/测试库"
.\.venv\Scripts\python.exe -m pyflakes backend scripts
.\.venv\Scripts\python.exe -m pytest backend/tests          # 每个用例使用独立的临时 schema
Set-Location frontend_Web
npm run build
Set-Location ..
.\.venv\Scripts\python.exe scripts/run_e2e.py                 # 浏览器测试：临时 schema + 临时服务，跑完即删
```

没有设置 `TEST_DATABASE_URL` 时，需要数据库的测试会被跳过。`scripts/run_e2e.py` 可以带 Playwright 参数，例如只跑某个文件。GitHub 上的 CI 会自动执行同样的检查（`.github/workflows/ci.yml`）。

**迁移**：在 `database/migrations/` 里新增 `V###__snake_name.sql`，并在文件里登记自己的版本；版本号不能与别人的重复（有测试检查）。

规模测试：`scripts/seed_scale_data.py` 生成大量合成数据，`scripts/benchmark_api.py` 给接口计时。

[框架设计](docs/phase-1-design.md) · [分享包说明](docs/share-guide.md)

第三方代码、模型和数据仍受原始许可约束。案例中的官方源码快照属于本机研究缓存，不提交仓库；固定版本及原始出处见资料清单和笔记。
