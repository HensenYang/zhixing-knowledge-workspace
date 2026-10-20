# 知行 · 具身智能知识工作台（协作者分享版）

打包日期：2026-10-20。解压后先阅读本文件。此包供协作者在自己的电脑上运行，不需要原作者的目录或数据库密码。

## 包含内容

- React / Vite 前端、FastAPI 后端、PostgreSQL 数据库迁移与 PowerShell 脚本。
- 笔记与关系编辑、全局／局部图谱、跟随阅读位置的关系导航、自由画布、学习日志、实验管理、回收站与备份恢复。
- `shared-data/knowledge-seed.zip`：当前有效的知识条目、关系与证据、画布、待运行实验，以及仍被引用的附件（如有）。个人学习日志、修订历史、回收站内容和已执行实验结果不进入共享种子。
- `research/unitree-group-01/`：宇树模型研究笔记、官方文本源码快照与出处。研究资料核对日期为2026-10-01，打包日期不代表已重新核对模型最新发布。
- `PACKAGE-MANIFEST.json`：包内文件 SHA256、资料数量及排除说明。

不包含 `.env`、数据库密码、Python 虚拟环境、node_modules、运行日志、测试截图、模型权重或大型数据集。安装时需要网络下载依赖；运行知识工作台本身不需要GPU。

## Windows 首次运行

准备 Python 3.12、Node.js 与 npm（前端 Vite 5 要求 Node 18 或 >=20），以及已启动的 PostgreSQL。确保 `python`、`node`、`npm` 在 PowerShell 中可用；数据库可使用协作者自己的主机、端口和管理员账号。

完整解压ZIP，进入包含本README的目录，勿直接在压缩包预览窗口里运行脚本。在该目录打开PowerShell，顺序执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\setup_database.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

数据库脚本会提示输入主机、端口、管理员账号与密码，创建 `embodied_knowledge` 数据库及 `knowledge_app` 账号；随机生成应用密码写入协作者本机 `.env`。不要将该文件再分享出去。已有同名账号、数据库或 `.env` 时脚本会停止并保留原配置；需使用合适的现有配置或独立 PostgreSQL 实例，勿删除原数据库。

启动后访问 http://127.0.0.1:5174/ 。端口8001和5174需要空闲。停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

脚本默认面向Windows；macOS/Linux需要手动创建虚拟环境、配置 `.env`，执行 `python scripts/migrate.py`，再分别启动 `uvicorn backend.app:app --host 127.0.0.1 --port 8001` 与前端 `npm run dev`。

## 选择空白使用或导入现有学习内容

空白使用：直接开始创建自己的知识条目即可。

导入宇树学习内容：在**空知识库**打开“环境与备份”，在“恢复备份”中选择 `shared-data/knowledge-seed.zip`，检查条目数量与ID冲突，点击“恢复已检查的备份”。不要先点击工作台的“建立首批学习对象”。重复导入会因ID冲突被拒绝，已有记录不会被覆盖。

恢复后刷新页面，通过“知识与资料”搜索“第一组研究”或“UnifoLM-VLA-0”，点击卡片进入阅读模式。阅读入口：

- 总览：http://127.0.0.1:5174/knowledge/d0c8d1fa-b8e9-4ab0-bcf3-bb1779e2fbd1
- VLA：http://127.0.0.1:5174/knowledge/13df8d24-5e4d-497f-99bf-0f5fd4ac3d98
- 研究画布：http://127.0.0.1:5174/canvases/a47b61eb-1a85-4ba1-a263-172c8b7662bd

右侧“沿关系阅读”可以按依赖、使用、比较等关系选择下一篇；局部图跟随当前笔记，支持展开。阅读路径保存在当前浏览器标签页的 sessionStorage 中，不随压缩包共享，也不等于已掌握。

## 协作方式和数据归属

这是本地单人工作台的分享包：每个人拥有自己的数据库副本，修改不会自动同步。整库备份适合交接到空库，不支持把多人的同ID修改自动合并。若后续需要多人共同维护同一套资料，需要另行设计共享部署、账号权限与冲突处理。

笔记、关系、画布、日志和实验记录保存在本机PostgreSQL；附件在项目的 `storage/` 下；尚未提交的草稿在浏览器IndexedDB。正式使用后请定期在“环境与备份”导出自己的备份。卸载前不要仅备份源码。

## 第三方材料与复现边界

官方源码快照与模型材料的出处保留在笔记及 `source-manifest.json` 中。第三方材料继续受其原始许可约束，来源与许可入口见 `THIRD-PARTY-SOURCES.md`。本包不重新授予第三方权重、代码或数据集的许可。

附带实验是待运行计划。下载权重、配置Linux／WSL2模型环境及GPU推理是后续独立步骤；本包不宣称已经完成模型复现。
