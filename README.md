# 知行 · Knowledge in Motion

A relationship-driven knowledge workspace for scientific communication and education.

将论文、代码、数据集、概念与实验连接成可探索、可追溯的学习路径。具身智能是当前案例，框架也可用于其他科学领域的研究交流与教学。

## 功能

- Markdown与公式笔记、来源和标签、版本冲突检查与浏览器草稿。
- 带类型及证据的知识关系、全局图谱和可编辑画布。
- 沿关系阅读：前置基座、方法应用、证据与横向比较；局部图跟随阅读位置并突出访问路径。
- 学习日志、待运行及已运行实验、附件、回收站、ZIP备份恢复。
- 用户登录、多人工作区、owner/editor/reviewer/viewer 权限、评论、版本审核和团队活动记录。

## 技术结构

React 18 / Vite 5 / Tailwind CSS，Cytoscape图谱与React Flow画布；Python / FastAPI；PostgreSQL。
前端地址 http://127.0.0.1:5174/ ，后端端口8001。首次打开时创建管理员账号；第一个账号会接管迁移前已有的本地资料。

## 多人协作

数据库迁移至 V003 后，内容按工作区隔离。所有者可在“团队协作”页面把已经注册的用户按邮箱加入当前工作区，并分配以下角色：

- owner：管理成员、编辑、评论和审核；
- editor：编辑内容、评论并提交版本审核；
- reviewer：只读内容、评论并批准或要求修改；
- viewer：只读内容和评论。

对象和画布继续使用版本号进行乐观并发控制；发生冲突时返回 409 并保留 IndexedDB 草稿，不会静默覆盖他人修改。备份只包含当前工作区的知识内容，不导出账号、密码、会话和成员权限。

远程部署必须由同一 HTTPS 域名提供前端与 `/api`，并设置 `COOKIE_SECURE=true`。PostgreSQL 不应暴露到公网，附件目录必须使用持久存储并纳入备份。本地开发保持 `COOKIE_SECURE=false`。

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

分享仓库或邀请协作者时请保持GitHub仓库为 Private。远程部署还需配置 HTTPS、持久附件存储、数据库备份和反向代理；当前版本使用版本冲突检测，不提供逐字实时共同编辑。

## 开发与验证

```powershell
Set-Location frontend_Web
npm run build
npx playwright test tests/reading-navigation.spec.js
```

阅读导航测试使用模拟接口。其他后端／浏览器验收可能写入测试数据，必须连接隔离测试数据库；参见测试代码中的 `TEST_DATABASE_URL` 配置，勿对个人正式数据库运行。

[框架设计](docs/phase-1-design.md) · [分享包说明](docs/share-guide.md)

第三方代码、模型和数据仍受原始许可约束。案例中的官方源码快照属于本机研究缓存，不提交仓库；固定版本及原始出处见资料清单和笔记。
