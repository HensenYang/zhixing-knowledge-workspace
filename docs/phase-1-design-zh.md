# 具身智能知识工作台：第一阶段规格

日期：2026-09-30；实现与验证更新于 2026-10-01。状态：首版已实现，独立测试 PostgreSQL 验收通过；用户已完成正式数据库初始化与启动，正式接口确认 database=ready、schema_version=V001，前端 HTTP 200。首次使用交互验收按 README 执行。

## 已确定的使用条件

- 本地浏览器访问、个人使用；当前项目独立于 UNSW_Helper。
- 已有 PyTorch 训练与复现经验；学习主线为机器人操作、VLA、世界模型。
- Windows 主机，系统报告版本 10.0.26200；具体 Windows 产品名称待确认。
- nvidia-smi：RTX 4090，24564 MiB 显存，驱动 610.47。
- 没有机器人或独立服务器；先本机离线推理与仿真。
- 不设每周固定时数；按阶段完成条件推进。学习任务可记录预估用时，但不要求填写。
- PostgreSQL 客户端 18.3，安装位置 A:/PostgreSQL；首次检查默认端口无响应，复查时 postgresql-x64-18 为 Running，127.0.0.1:5432 接受连接。尚未进行账号认证或应用数据库连接，服务就绪不等于应用连接已验证。

## 技术选择及证据

参考项目 A:/WeChat_Mini_programs/UNSW_Helper：

- frontend_Web/package.json 与 src/App.jsx：JavaScript/JSX、React 18、React Router 6、Vite 5、Tailwind 3；另有 Tiptap 富文本编辑器。
- frontend_Web/vite.config.js：开发前端 5173，/api 代理至本地 8000。
- backend/requirements.txt、src/db/connection.py：Python、FastAPI、Pydantic、Uvicorn、psycopg2；显式 SQL 和数据库连接池。
- database/flyway/sql：版本化 SQL 迁移。

新项目确定：JavaScript/JSX + React + Vite + Tailwind + React Router；Python + FastAPI + Pydantic + psycopg2；PostgreSQL 18。实际采用已有 Python 3.12.7 创建独立 .venv，已验证当前依赖兼容，无需修改模型环境。
使用 JavaScript 保持与参考项目一致；对象字段通过 Pydantic 和前端 JSDoc 约束。依赖具体版本在安装时按兼容性固定，不照搬参考项目的完整依赖清单。
新增 React Flow（@xyflow/react）处理画布，Cytoscape.js 处理知识网络。Markdown 为第一版正文来源，支持公式和代码块；Tiptap 暂不采用，避免双格式往返。
版本化 SQL 延续 Flyway 文件命名习惯，但新项目不要求安装 Flyway：最初通过 psql 顺序应用迁移并记录已应用版本。

## 项目结构与运行边界

```text
Model_Research/
  docs/                         规格、操作说明、设计决策
  frontend_Web/
    src/components/             编辑器、关系编辑器、图谱、画布、公共控件
    src/pages/                  工作台、知识、图谱、画布、轨迹、实验、设置
    src/services/               API 请求和响应处理
    src/hooks/                  自动保存、查询、快捷键
    src/utils/                  图数据转换、导入导出、格式化
    src/styles/                 Tailwind 入口和组件局部样式
  backend/
    src/api/                    对象、关系、画布、日志、实验、附件、导出
    src/core/                   环境设置和日志
    src/db/                     连接、显式 SQL repositories、事务
    src/services/               跨表业务和备份恢复
  database/migrations/          版本化 SQL
  storage/attachments/          小型资料附件，数据库仅存相对路径
  storage/exports/              导出包
  experiments/                 实验代码和配置，模型环境独立
```

开发建议前端 5174、后端 8001，避免与参考项目常用端口冲突。仅绑定 127.0.0.1；前端通过 /api 代理访问后端。开发端口若占用则明确报错。
数据库建议新建 embodied_knowledge，应用 schema 为 knowledge；独立应用账号。不使用参考项目数据库或复制其连接密码。
模型权重与大型数据集保存在独立目录；工作台保存路径、版本、大小与可选校验值。模型实验环境与知识库环境分离。
数据库凭据通过本地 .env 配置，提交 .env.example；不把凭据放在浏览器或文档里。数据库创建与连通性是下一步运行接入工作。

## 页面规格

全局布局：左侧导航，中间工作区，右侧可折叠详情；顶部全局搜索与新增。优先桌面浏览器。默认主题采用适合长时间阅读的简洁界面；参考项目的 PlayStation 视觉风格不作为本项目要求。

| 路由 | 默认内容 | 核心操作与完成条件 |
|---|---|---|
| / | 当前问题、下一步任务、最近活动、待整理资料 | 从首页打开当前工作，无需填写时数 |
| /knowledge | 按类型、主题、阅读状态筛选的对象列表 | 新建、搜索、归档，进入详情 |
| /knowledge/:id | Markdown 正文、属性、来源、反向关系、局部图 | 修改标题保留连接；查看一到两层邻居 |
| /graph | 按类型着色的全局知识网络 | 搜索、过滤、展开、选择节点或边、编辑关系 |
| /canvases | 保存的主题／问题画布 | 新建、重命名、打开 |
| /canvases/:id | 自由画布及可拖入对象列表 | 拖拽、缩放、分组、连线、撤销；刷新恢复布局 |
| /timeline | 学习日志和实验事件时间线 | 查看关联对象、记录理解变化和下一步 |
| /experiments | 按问题组织的实验与运行记录 | 录入命令、配置、版本、指标和失败原因 |
| /settings | 环境信息、备份、恢复 | 校验导入文件；完整恢复到干净测试库 |

所有编辑有明确的保存中／已保存／失败状态。服务不可用时保留当前草稿并可重试，不显示虚假成功。导入先预览并检测 ID 冲突；删除优先归档，硬删除仅用于显式清理。

## 对象与关系

对象类型：concept、resource、repository、model、dataset、benchmark、experiment、question、task。
resource 子类型为 paper、blog、course、documentation。日志与运行记录单独保存，连接到对象。
对象共用 UUID、标题、Markdown 正文、说明、阅读状态、掌握状态、来源地址、metadata、版本号、时间戳和归档时间。
阅读状态与掌握状态分开：unread/skimming/reading/organized 与 unknown/explain/implement/reproduce/analyze。
repository metadata 包含 commit；model 包含权重版本、输入输出；resource 包含 DOI/arXiv、作者、年份、页码笔记；task 包含验收条件。API 按 kind 验证 metadata。

关系是独立记录，箭头方向明确：A depends_on B 表示 A 依赖 B；repository implements resource；run 通过实验对象关联 evaluates；结果 supports/questions 某问题或假设。
关系类型初始为 depends_on、implements、uses、evaluates、supports、questions、compares_with、related_to。compares_with/related_to 采用无向展示，写入时规范化端点顺序，避免重复。
关系可附证据对象、页码／章节／行号定位和自己的解释。多条独立证据保存在 relation_evidence。掌握状态只允许用户明确更新，浏览行为不自动代表掌握。

## 画布语义

知识对象与画布实例分开。一个对象可在多个画布，甚至在同一画布出现多次；每个实例独立 ID、位置、大小和分组。
画布 item 可为 object/text/group；object 引用对象 ID，text/group 保存自身内容。
画布 edge 默认为局部连线；提升为知识关系需选择类型和说明。已有知识关系可引用到画布。删除画布连线只移除该画布呈现，知识关系删除通过独立命令执行。
知识关系被删除后，其画布连线转为局部连线并显示状态。改标题同步所有引用；不同画布布局互不影响。
图谱只展示已保存知识关系，不将所有画布线自动转换成事实。自动布局不覆盖其他画布的手工位置。

## API 与保存策略

- /api/objects：CRUD、过滤、分页；PATCH 带 version，旧版本返回 409，避免覆盖另一标签页的修改。
- /api/relations：创建、改类型／说明、删除、证据管理；/api/graph?center=&depth= 返回对象和关系。
- /api/canvases：CRUD；PUT /:id/document 原子保存 items、edges、viewport，并检查 version。
- /api/sessions：日志及关联对象；/api/runs：实验运行和产物。
- /api/attachments：上传、读取、引用；拒绝路径穿越，浏览器只使用附件 ID。
- /api/export 与 /api/import：版本化清单、全部表数据、附件、可选外部产物清单。
- /api/health：服务与数据库分别显示连接状态。

编辑防抖保存，离开页面时提示未保存状态；IndexedDB 只作为未提交草稿缓存，服务端数据库为最终来源。对象修订保存快照，画布以历史快照支持关键撤销和恢复。
检索第一版支持标题、正文、标签、类型；中文先采用子串匹配，不承诺 PostgreSQL 内置英文全文分词能正确处理中文。规模增大后再评估 pg_trgm 或中文检索方案。

## 执行顺序与验收

1. 环境接入：确认数据库 host/port/数据库名/应用账号，验证认证连接并建立独立数据库。服务已在复查时运行；凭据本地填写。
2. 工程骨架：前后端可启动、健康检查、数据库版本迁移；确认端口与独立环境。
3. 纵向闭环：对象录入、正文、关系、局部图；持久化和失败提示。
4. 图谱与画布：编辑连接、引用同一对象、多画布保存、分组与撤销。
5. 轨迹与实验：日志、运行、指标、产物、下一步关联。
6. 导出恢复：在干净测试库验证数据与附件完整性。
7. 通过以下验收后，进入第一组机器人学习实验。

验收用例：UnifoLM-WMA-0 模型对象 → 官方仓库 → 世界模型概念 → “4090 可运行哪种配置”问题 → 一条资料调查日志。包含中英文与公式内容，至少两个画布引用同一对象。
必须验证：关系类型可修改；对象改名不丢连接；布局刷新保留且相互独立；局部线不污染全局图；删除可恢复；重启服务后记录保留；导出恢复保留 ID、正文、关系、证据、布局、日志和附件；多个标签页编辑不静默覆盖。
数据库约束、原子保存、版本冲突和备份恢复需要针对性测试；纯布局改动通过浏览器检查。

## 学习开始后的节奏

第一组任务不按日历硬排：读懂一段机器人轨迹 → 解释观测和动作单位 → 跑通小型模仿学习任务 → 保存失败案例与可重复配置。
每一阶段都有完成条件；下一任务根据缺口和实验结果生成。没有固定时数不影响推进。

## 参考文档

- React Flow 保存恢复：https://reactflow.dev/examples/interaction/save-and-restore
- PostgreSQL JSONB：https://www.postgresql.org/docs/current/datatype-json.html
- Vite：https://vite.dev/guide/
- FastAPI：https://fastapi.tiangolo.com/
