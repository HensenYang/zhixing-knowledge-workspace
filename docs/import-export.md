# 轻量资料导入与导出

## 支持的导入来源

- arXiv URL 或标识符
- DOI URL 或标识符（元数据来自 Crossref）
- GitHub 仓库 URL（公开仓库无需 Token）
- 本地 PDF，单个文件上限 32 MB
- 本地 Zotero 文献库：通过 kujenga/zotero-mcp 搜索、读取元数据与已索引全文
- 可选 MCP Streamable HTTP Server

所有来源都采用“提取并预览 → 用户修改 → 确认入库”的流程。预览不会写入数据库；同一个来源确认导入后不能再次导入，已有知识对象不会被覆盖。

PDF 使用自适应文本提取：默认保留 PDF 的原始文本顺序；如果检测到文本层被按单词拆成大量短行，会自动改用页面布局重排，并在导入预览中提醒用户检查表格、多栏或代码排版。当前不包含 OCR；扫描版 PDF 如果没有文本层，会显示警告，用户仍可补充标题和正文后入库。PDF 预览会提取位图并为矢量图形保留整页预览，确认后原文件与图片统一保存为附件，正文引用自动转换为永久链接。

## MCP 配置

通用 MCP 来源通过本机 `.env` 中配置的 Streamable HTTP Server 连接。Zotero 专用来源另行支持下文所述的本机 stdio 命令；浏览器不能指定或执行命令。

```dotenv
MCP_IMPORT_SERVER_URL=http://127.0.0.1:3001/mcp
MCP_IMPORT_TOOL=import_source
MCP_IMPORT_ARGUMENT=source
```

未配置 `MCP_IMPORT_SERVER_URL` 时，资料导入页面不会显示 MCP 选项。

配置的工具接收一个字符串参数，例如：

```json
{"source": "https://example.org/paper"}
```

推荐返回结构化内容：

```json
{
  "title": "资料标题",
  "summary": "简短摘要",
  "body_md": "Markdown 正文",
  "source_url": "https://example.org/paper",
  "kind": "resource",
  "tags": ["论文"],
  "metadata": {"authors": "作者"},
  "warnings": []
}
```

如果工具只返回文本，系统会把它作为 Markdown 正文。MCP 结果仍需用户确认，不能直接创建知识关系。

## 本地 Zotero MCP

支持 `kujenga/zotero-mcp@0.3.1` 的三个只读工具：`zotero_search_items`、`zotero_item_metadata`、`zotero_item_fulltext`。先打开 Zotero 并允许本机应用通信，然后配置：

```dotenv
ZOTERO_MCP_ENABLED=true
ZOTERO_MCP_COMMAND=uvx
ZOTERO_MCP_ARGS=["zotero-mcp@0.3.1"]
```

`ZOTERO_MCP_ARGS` 必须为 JSON 字符串数组。启动命令由后端本机配置决定；子进程固定使用 `ZOTERO_LOCAL=true` 和当前本机用户库，不自动复用其他客户端配置，不接收浏览器传来的命令。修改后重启后端。

在资料导入页选择“Zotero（本地文献库）”，搜索并选择条目，再读取预览。全文和图片附件可以分别选择；同时关闭两项时只读取元数据。全文缺失或读取失败时会明确警告，允许继续导入元数据。文献正文、标题和标签保持原文，切换界面语言不会翻译或重置预览。预览正文上限为 200,000 字符，超长时显示截断提示。

搜索和预览不写入知识对象，确认后才写入。Zotero 导入沿用 `source_type=mcp`，`source_key` 为 `zotero:local:0:{item_key}`；同一有效来源会提示打开已有资料或另存独立笔记；旧对象在回收站时允许重新导入，不覆盖回收站中的旧资料。元数据保留 Zotero 定位 URI 和全文是否包含的标记；勾选图片附件选项时，会从 Zotero 本机 API 获取原始 PDF，提取图片并在确认时复制到工作台；没有原 PDF 时保留文本并提示。

完整配置、操作步骤和接口参数见 [中文 README](../README_zh.md) 与 [English README](../README.md)。

## LLM 解析与重复导入

预览中点击“使用 LLM 解析”将当前标题、摘要和正文发送到本机配置的模型。输出语言遵循文献主要语言，与界面语言无关。生成摘要、方法、结论和局限，正文保留原文和图片；图片二进制不会发送，暂不做 OCR。解析不会自动保存，检查编辑后需再次确认。长文仅分析开头、中间、结尾合计最多 48,000 个字符，并明确标注范围。元数据保留模型、检测语言、时间、输入哈希与覆盖数量。

- `POST /api/source-imports/analyze`：输入 `title`、`summary`、`body_md`，返回结构化解析和来源范围，不访问数据库。
- 预览返回 `existing_import`（存在时包含 `id`、`title`、`deleted_at`）。回收站内的旧资料允许重新导入，原对象及其附件不会改写。
- 确认可传 `save_as_note=true` 创建独立笔记，以 `metadata.derived_source` 保留来源及旧对象定位；不抢占来源的唯一导入记录。
- 已有有效导入且未选择另存时返回 409，`detail.message` 与 `detail.existing_import` 供界面显示具体提示和链接；附件预览保持可用，供用户重新选择保存方式。

操作流程及限制同时见 [English README](../README.md#analyze-an-import-with-an-llm)。

## 导出

打开任意知识详情，在右侧“导出资料”中选择：

- Markdown：保留原始 Markdown，适合 Git 和 Obsidian。
- Word：生成 `.docx`，适合继续编辑和提交。
- PDF：生成带中文字体映射的 `.pdf`，适合阅读、打印和分享。

导出内容包括当前知识对象的标题、类型、标签、来源、摘要、正文、相关知识、关系证据、附件清单和扩展属性。导出前页面会先保存未提交的草稿；保存失败时不会导出旧版本。

## 数据库迁移

现有数据库升级后执行：

```powershell
.\.venv\Scripts\python.exe scripts\migrate.py
```

迁移 `V003` 只增加资料来源记录表，不会修改现有知识正文。数据库 ZIP 备份格式升级为版本 2，同时仍可导入旧版版本 1 备份。

## 图片资源与 HTML

本地 PDF 和 Zotero PDF 使用 PyMuPDF 提取位图可见区域，并为含矢量绘图的页面保留整页 PNG。不会自动理解图表，也不会做 OCR。正文以页码定位图片；去重后的图片与原始 PDF 暂存于 `storage/import-previews/`，不写入知识对象。两小时内确认时通过一次数据库事务保存对象、来源与附件记录，同时将 `import-asset://...` 引用改为 `/api/attachments/{id}/content`。复制或数据库提交失败时清理目标文件，保留预览重试；成功后移除临时资源。过期临时目录在后续 PDF 提取时清理。

预览资源接口为 `GET /api/source-imports/assets/{token}/{asset_id}`；确认时向既有接口额外传入 `preview_token`。前端不会再次上传同一份原 PDF。正文、附件和 ZIP 备份共用稳定附件 ID。单份 PDF 32 MB、最多处理 200 页、80 张去重图像、资源合计 72 MB；图片最长边最高 1,800 像素。

GitHub 导入保留 `metadata.readme_path`。阅读页和导入预览根据来源仓库、README 目录与 commit 解析 Markdown/HTML 的相对图片和文档路径，因此已有笔记不需要改写。GitHub 图片保持远程引用，不做任意 URL 下载。HTML 使用 `rehype-raw` 与 `rehype-sanitize` 解析并清理，兼容居中标题、图片、表格、折叠区块、章节锚点和数学公式；脚本和事件属性不执行。
