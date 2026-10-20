# 轻量资料导入与导出

## 支持的导入来源

- arXiv URL 或标识符
- DOI URL 或标识符（元数据来自 Crossref）
- GitHub 仓库 URL（公开仓库无需 Token）
- 本地 PDF，单个文件上限 32 MB
- 可选 MCP Streamable HTTP Server

所有来源都采用“提取并预览 → 用户修改 → 确认入库”的流程。预览不会写入数据库；同一个来源确认导入后不能再次导入，已有知识对象不会被覆盖。

PDF 使用文本提取，不包含 OCR。扫描版 PDF 如果没有文本层，会显示警告，用户仍可补充标题和正文后入库。确认 PDF 导入后，原文件会作为该知识对象的附件上传。

## MCP 配置

项目是 MCP Client，不会启动或执行任意本地 MCP 命令。当前仅接受在本机 `.env` 中配置的 Streamable HTTP Server：

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
