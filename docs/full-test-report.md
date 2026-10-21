# 完整回归测试 / Full regression

日期 / Date: 2026-10-22

## 结果 / Results

最终完整回归全部通过 / The final full regression passed.

| 检查 / Check | 结果 / Result |
| --- | --- |
| 后端单元与真实数据库集成 / Backend units and database integration | 116 passed, 0 failed, 0 skipped |
| 前端单元 / Frontend units | 11 passed, 0 failed |
| Chrome 浏览器场景 / Chrome scenarios | 32 passed, 0 failed |
| `npm run check:i18n` | Passed: 906 paired messages |
| `npm run test:i18n` / `npm run test:artifacts` | Passed: 5 / 3 tests; included in the 11 frontend unit cases above |
| `npm run build` | Passed |
| `git diff --check` / Python compile checks | Passed |

本轮原始证据 / Run evidence:

- [全部阶段退出状态 / Stage results](../storage/full-tests/20261022-050225/summary.json)
- [后端 JUnit XML / Backend JUnit](../storage/full-tests/20261022-050225/backend.xml)
- [浏览器逐场景结果 / Browser results](../storage/full-tests/20261022-050225/browser-fallback.json)
- [笔记截图 / Note screenshot](../storage/screenshots/note.png)
- [画布截图 / Canvas screenshot](../storage/screenshots/canvas.png)

原始日志、截图和临时数据库目录属于本机测试产物，由 Git 忽略；测试代码和本报告保存在仓库中。

Raw logs, screenshots, and disposable database files are local ignored artifacts. Test sources and this report are kept in the repository.

## 测试环境 / Environment

使用新建的 PostgreSQL 实例、独立文件存储、临时 API 和前端端口，以及真实 Chrome。最终回归使用普通数据库角色，保留 PostgreSQL 的行级权限检查。没有读取个人 `.env`，没有写入日常数据库或 Zotero 文献库，也没有调用付费模型。

The final run uses a fresh PostgreSQL cluster, a non-superuser database role, isolated storage, temporary API/frontend ports, and real Chrome. Personal configuration and data are untouched. No paid model requests are made.

## 覆盖范围 / Coverage

| 功能 / Feature | 检查内容 / Checks |
| --- | --- |
| 资料导入 / Source import | 真实 PDF 提取、预览不写库、修改标题/摘要/标签后确认、原 PDF 附件下载、图片与正文引用、重复导入、删除后重新导入、不同工作区分别导入同一来源 |
| 知识笔记 / Knowledge notes | 界面新建、自动保存、切换语言保留草稿、刷新恢复、搜索、版本历史、冲突保留、公式/代码渲染、HTML 清理 |
| 学习路径 / Learning paths | 界面创建、添加知识对象、编辑提示/完成条件/用时、步骤重排、保存刷新、发布、匿名只读浏览、停止分享 |
| Artifact | HTML/JSON 导出、断网浏览 HTML、关键信息和关系证据、正文开关、文件导入预览、保存独立副本、ID 重映射、恶意 HTML 不执行、只读角色限制 |
| 自由画布 / Canvas | 卡片连线、编辑连线、转为正式知识关系、拖动位置、撤销、分组、刷新恢复、画布重命名、版本冲突与事务原子性 |
| 图谱和记录 / Graph and records | 节点/关系编辑、删除与恢复、证据保留、归档、回收站永久删除确认、学习日志、实验运行、备份恢复 |
| 协作与界面 / Collaboration and UI | 登录限制、工作区隔离、成员权限、评论与审核、桌面/窄屏导航、中英文切换与跨标签同步、未捕获的浏览器异常 |

PDF import, notes, paths, canvases, record management, and persistence are tested against the real API and database. Browser adapter/error scenarios also use mocked APIs to exercise cases deterministically.

## 本轮修复 / Fixes

资料确认导入的 `ON CONFLICT` 仍使用旧的 `(source_type, source_key)`，而多工作区迁移后唯一约束已改为 `(workspace_id, source_type, source_key)`，导致导入返回 503。已修复冲突目标，并添加同一工作区重复来源冲突、不同工作区分别导入且互不覆盖的回归检查；无需新增迁移。

Source import used an obsolete conflict target and failed after the collaboration migration. The upsert now matches the workspace-scoped unique constraint. Regression tests verify duplicate rejection within one workspace and independent imports across workspaces.

旧的 LLM、资料分析、Zotero 处理器单元测试和部分浏览器 mock 尚未适配登录机制。单元测试现在使用独立 FastAPI 处理器/路由入口；真实应用的认证与权限由数据库集成测试验证。生产登录中间件保持启用。

Older handler and mocked browser tests now account for authentication. Handler contract tests use isolated apps; integration tests retain the actual authentication middleware.

## 复现 / Reproduce

在仓库根目录运行，使用现有虚拟环境、已安装的 PostgreSQL 程序和 Node。脚本始终新建测试实例，不接受个人数据库连接串。

Run from the repository root. The runner always initializes a disposable cluster and never accepts a personal database URL.

```powershell
.\.venv\Scripts\python.exe scripts/verify_full.py --browser-fallback
```

若程序位置不同，可传入 `--postgres-bin "C:\path\pgsql\bin" --node "C:\path\node.exe"`。默认使用项目本地 `storage/runtime` 中的程序。需要已安装 Chrome。

Use `--postgres-bin` and `--node` to supply other installed runtimes. Chrome is required.

默认不带 `--browser-fallback` 时使用 Playwright CLI。本机 CLI 工作进程启动停滞，因此本次使用单进程后备执行器：执行相同的 spec 函数、Playwright 浏览器操作和 `expect` 断言，每个场景创建新浏览器上下文。后备执行器仅支持当前测试用到的 `page/context/browser` 和 `beforeEach`，每个场景上限为 90 秒。

The standard runner is available by omitting `--browser-fallback`. The fallback executes the same specs with real Playwright browsers and assertions, using a fresh context per scenario; it is limited to the fixtures currently used by this repository.

日志和结果保存在 `storage/full-tests/<时间戳>/`；包括后端 JUnit XML、浏览器逐场景 JSON、构建日志和失败截图。测试结束后自动停止临时服务。`--spec full-workflow.spec.js` 可限制浏览器场景，后端和构建检查仍会完整运行。

Logs, JUnit XML, browser JSON, build output, and failure screenshots are kept under `storage/full-tests/<timestamp>/`. Temporary services stop when the run ends.

## 范围边界 / Limits

外部 LLM 服务、真实 Zotero 连接和在线 arXiv/DOI/GitHub 可用性使用 mock/适配器契约验证；本次结果不代表这些外部服务在某个网络或密钥下的可用性。PDF 使用自动生成的测试资料，未穷举所有扫描件、字体或复杂版式。窄屏检查覆盖导航与主要页面，未对所有设备做视觉兼容测试。未执行负载测试。

External services use deterministic mocks/adapter contracts. This run does not certify live provider availability, every possible PDF layout, every device, or load capacity.
