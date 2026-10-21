"""Lightweight source import providers.

Providers return a common preview shape. Nothing in this module writes to the
knowledge database: the user must review the preview before the API commits it.
"""
from __future__ import annotations

import base64
import asyncio
import hashlib
import html
import io
import json
import os
import re
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree

import httpx
from fastapi import HTTPException
from pypdf import PdfReader


MAX_PDF_BYTES = 32 * 1024 * 1024
MAX_BODY_CHARS = 200_000
USER_AGENT = "KnowledgeInMotion/0.2 (local research workspace)"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strip_markup(value: str) -> str:
    return _clean(html.unescape(re.sub(r"<[^>]+>", " ", value or "")))


def _trim_body(value: str, warnings: list[str]) -> str:
    value = value.strip()
    if len(value) <= MAX_BODY_CHARS:
        return value
    warnings.append(f"正文超过 {MAX_BODY_CHARS:,} 个字符，预览和入库内容已截断。")
    return value[:MAX_BODY_CHARS].rstrip() + "\n\n> 导入时已截断。"


def _preview(
    *, source_type: str, source_key: str, source_url: str | None,
    title: str, summary: str = "", body_md: str = "", kind: str = "resource",
    tags: list[str] | None = None, metadata: dict | None = None,
    warnings: list[str] | None = None,
) -> dict:
    warnings = warnings or []
    return {
        "source_type": source_type,
        "source_key": source_key,
        "source_url": source_url,
        "title": title.strip() or source_key,
        "summary": summary.strip(),
        "body_md": _trim_body(body_md, warnings),
        "suggested_kind": kind,
        "tags": sorted({tag.strip() for tag in (tags or []) if tag.strip()}),
        "metadata": metadata or {},
        "warnings": warnings,
    }


def detect_source_type(source: str) -> str:
    value = source.strip()
    lower = value.lower()
    if "github.com/" in lower:
        return "github"
    if "arxiv.org/" in lower or re.fullmatch(r"(?:[a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", lower):
        return "arxiv"
    if lower.startswith("doi:") or "doi.org/" in lower or re.fullmatch(r"10\.\d{4,9}/\S+", value, re.I):
        return "doi"
    raise HTTPException(422, "无法识别资料来源。请选择 arXiv、DOI、GitHub 或 MCP。")


async def _get(url: str, *, headers: dict | None = None) -> httpx.Response:
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/plain"}
    merged.update(headers or {})
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, headers=merged) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "资料来源响应超时，请稍后重试。") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 404:
            raise HTTPException(404, "没有找到对应资料，请检查标识符或链接。") from exc
        if status == 403:
            raise HTTPException(502, "资料来源拒绝访问或已达到调用限额。") from exc
        raise HTTPException(502, f"资料来源返回错误（HTTP {status}）。") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "无法连接资料来源，请检查网络后重试。") from exc


def _arxiv_id(source: str) -> str:
    value = source.strip()
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+)", value, re.I)
    identifier = (match.group(1) if match else value).removesuffix(".pdf")
    if not re.fullmatch(r"(?:[a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", identifier, re.I):
        raise HTTPException(422, "arXiv 标识符格式无效。")
    return identifier


async def import_arxiv(source: str) -> dict:
    identifier = _arxiv_id(source)
    response = await _get(f"https://export.arxiv.org/api/query?id_list={quote(identifier, safe='')}")
    try:
        root = ElementTree.fromstring(response.text)
    except ElementTree.ParseError as exc:
        raise HTTPException(502, "arXiv 返回了无法解析的内容。") from exc
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise HTTPException(404, "没有找到对应的 arXiv 论文。")
    title = _clean(entry.findtext("atom:title", default="", namespaces=ns))
    abstract = _clean(entry.findtext("atom:summary", default="", namespaces=ns))
    published = entry.findtext("atom:published", default="", namespaces=ns)
    authors = [_clean(item.findtext("atom:name", default="", namespaces=ns)) for item in entry.findall("atom:author", ns)]
    pdf_url = next((item.attrib.get("href") for item in entry.findall("atom:link", ns) if item.attrib.get("title") == "pdf"), None)
    source_url = f"https://arxiv.org/abs/{identifier}"
    return _preview(
        source_type="arxiv", source_key=identifier.lower(), source_url=source_url,
        title=title or identifier, summary=abstract,
        body_md=f"## 摘要\n\n{abstract}" if abstract else "",
        tags=["arXiv", "论文"],
        metadata={
            "subtype": "paper", "arxiv": identifier, "authors": ", ".join(authors),
            "year": published[:4], "published": published, "pdf_url": pdf_url or "",
            "import_provider": "arxiv",
        },
    )


def _doi(source: str) -> str:
    value = source.strip()
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
    if not re.fullmatch(r"10\.\d{4,9}/\S+", value, re.I):
        raise HTTPException(422, "DOI 格式无效。")
    return value


async def import_doi(source: str) -> dict:
    identifier = _doi(source)
    response = await _get(f"https://api.crossref.org/works/{quote(identifier, safe='')}")
    try:
        item = response.json()["message"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, "DOI 服务返回了无法解析的内容。") from exc
    title = _clean((item.get("title") or [identifier])[0])
    abstract = _strip_markup(item.get("abstract", ""))
    authors = [" ".join(filter(None, [author.get("given", ""), author.get("family", "")])).strip() for author in item.get("author", [])]
    date_parts = ((item.get("published-print") or item.get("published-online") or item.get("issued") or {}).get("date-parts") or [[]])[0]
    year = str(date_parts[0]) if date_parts else ""
    journal = _clean((item.get("container-title") or [""])[0])
    return _preview(
        source_type="doi", source_key=identifier.lower(),
        source_url=item.get("URL") or f"https://doi.org/{identifier}",
        title=title, summary=abstract,
        body_md=f"## 摘要\n\n{abstract}" if abstract else "",
        tags=["DOI", "论文"],
        metadata={
            "subtype": "paper", "doi": identifier, "authors": ", ".join(authors),
            "year": year, "journal": journal, "publisher": _clean(item.get("publisher")),
            "import_provider": "crossref",
        },
    )


def _github_repo(source: str) -> tuple[str, str]:
    match = re.match(r"^https?://github\.com/([^/]+)/([^/#?]+)", source.strip(), re.I)
    if not match:
        raise HTTPException(422, "GitHub 链接格式无效，请输入仓库主页链接。")
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise HTTPException(422, "GitHub 仓库名称包含无效字符。")
    return owner, repo


async def import_github(source: str) -> dict:
    owner, repo = _github_repo(source)
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    base = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
    response = await _get(base, headers=headers)
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(502, "GitHub 返回了无法解析的内容。") from exc
    warnings: list[str] = []
    readme = ""
    commit = ""
    try:
        readme_response = await _get(f"{base}/readme", headers=headers)
        payload = readme_response.json()
        if payload.get("encoding") == "base64":
            readme = base64.b64decode(payload.get("content", ""), validate=False).decode("utf-8", errors="replace")
    except HTTPException as exc:
        if exc.status_code != 404:
            warnings.append("README 获取失败，已保留仓库元数据。")
    branch = data.get("default_branch") or ""
    if branch:
        try:
            commit_response = await _get(f"{base}/commits/{quote(branch, safe='')}", headers=headers)
            commit = _clean(commit_response.json().get("sha"))
        except HTTPException:
            warnings.append("默认分支 commit 获取失败，可在扩展属性中手动补充。")
    tags = ["GitHub", "代码仓库"]
    if data.get("language"):
        tags.append(str(data["language"]))
    return _preview(
        source_type="github", source_key=f"{owner}/{repo}".lower(),
        source_url=data.get("html_url") or f"https://github.com/{owner}/{repo}",
        title=data.get("full_name") or f"{owner}/{repo}", summary=_clean(data.get("description")),
        body_md=readme, kind="repository", tags=tags, warnings=warnings,
        metadata={
            "commit": commit, "default_branch": branch, "language": data.get("language") or "",
            "license": ((data.get("license") or {}).get("spdx_id") or ""),
            "stars": data.get("stargazers_count", 0), "import_provider": "github",
        },
    )


def _pdf_text_stats(text: str) -> dict[str, float | int]:
    """Measure whether extracted PDF text was split into many tiny lines."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {
            "line_count": 0,
            "single_token_ratio": 0.0,
            "short_line_ratio": 0.0,
            "median_chars": 0.0,
            "nonspace_chars": 0,
        }

    character_counts = sorted(len(re.sub(r"\s+", "", line)) for line in lines)
    middle = len(character_counts) // 2
    if len(character_counts) % 2:
        median_chars = float(character_counts[middle])
    else:
        median_chars = (character_counts[middle - 1] + character_counts[middle]) / 2
    single_token_lines = sum(len(re.findall(r"\S+", line)) == 1 for line in lines)
    short_lines = sum(character_count <= 20 for character_count in character_counts)
    return {
        "line_count": len(lines),
        "single_token_ratio": single_token_lines / len(lines),
        "short_line_ratio": short_lines / len(lines),
        "median_chars": median_chars,
        "nonspace_chars": sum(character_counts),
    }


def _pdf_text_is_fragmented(text: str) -> bool:
    stats = _pdf_text_stats(text)
    return bool(
        stats["line_count"] >= 20
        and stats["single_token_ratio"] >= 0.60
        and stats["short_line_ratio"] >= 0.70
        and stats["median_chars"] <= 15
    )


def _normalize_pdf_layout_text(text: str) -> str:
    """Remove layout-mode spacing while preserving paragraphs and page structure."""
    normalized_lines = [
        re.sub(r"[^\S\r\n]+", " ", line).strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(normalized_lines)).strip()


def _pdf_layout_is_better(plain_text: str, layout_text: str) -> bool:
    if not layout_text:
        return False
    plain_stats = _pdf_text_stats(plain_text)
    layout_stats = _pdf_text_stats(layout_text)
    plain_characters = int(plain_stats["nonspace_chars"])
    retained_characters = (
        int(layout_stats["nonspace_chars"]) / plain_characters
        if plain_characters
        else 0.0
    )
    fragmentation_improvement = (
        float(plain_stats["single_token_ratio"])
        - float(layout_stats["single_token_ratio"])
    )
    line_reduction = (
        int(layout_stats["line_count"]) <= int(plain_stats["line_count"]) * 0.60
    )
    return bool(
        retained_characters >= 0.85
        and (fragmentation_improvement >= 0.25 or line_reduction)
    )


def import_pdf(content: bytes, filename: str) -> dict:
    if not content:
        raise HTTPException(422, "PDF 文件为空。")
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF 文件不能超过 32 MB。")
    if not filename.lower().endswith(".pdf") or not content.startswith(b"%PDF"):
        raise HTTPException(422, "请选择有效的 PDF 文件。")
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise HTTPException(422, "暂不支持加密 PDF。")
        metadata = reader.metadata or {}
        pages = []
        layout_reflow_pages = []
        for index, page in enumerate(reader.pages, start=1):
            plain_text = (page.extract_text() or "").strip()
            text = plain_text
            if _pdf_text_is_fragmented(plain_text):
                try:
                    layout_text = _normalize_pdf_layout_text(
                        page.extract_text(extraction_mode="layout") or ""
                    )
                except Exception:
                    # A malformed layout stream should not discard usable plain text.
                    layout_text = ""
                if _pdf_layout_is_better(plain_text, layout_text):
                    text = layout_text
                    layout_reflow_pages.append(index)
            if text:
                pages.append(f"## 第 {index} 页\n\n{text}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "PDF 无法解析，文件可能已损坏或使用了不支持的编码。") from exc
    warnings = []
    if not pages:
        warnings.append("未提取到正文；扫描版 PDF 需要 OCR，当前版本不会自动识别图片文字。")
    if layout_reflow_pages:
        page_list = "、".join(str(page) for page in layout_reflow_pages)
        warnings.append(
            f"检测到 PDF 文字层按词碎片化，已按页面布局自动重排第 {page_list} 页；"
            "表格、多栏或代码排版可能仍需在保存前检查。"
        )
    digest = hashlib.sha256(content).hexdigest()
    title = _clean(metadata.get("/Title")) or filename.rsplit(".", 1)[0]
    author = _clean(metadata.get("/Author"))
    subject = _clean(metadata.get("/Subject"))
    return _preview(
        source_type="pdf", source_key=digest, source_url=None, title=title,
        summary=subject, body_md="\n\n".join(pages), tags=["PDF"], warnings=warnings,
        metadata={
            "subtype": "paper", "file_name": filename, "pages": len(reader.pages),
            "authors": author, "sha256": digest, "import_provider": "pypdf",
            "pdf_extraction_mode": "adaptive-layout" if layout_reflow_pages else "plain",
            "layout_reflow_pages": layout_reflow_pages,
        },
    )


def _mcp_data(result: Any) -> dict:
    data = result.structured_content
    if isinstance(data, dict) and set(data) == {"result"}:
        data = data["result"]
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            data = {"body_md": data}
    if not isinstance(data, dict):
        texts = [getattr(block, "text", "") for block in result.content if getattr(block, "type", "") == "text"]
        text = "\n\n".join(filter(None, texts))
        try:
            data = json.loads(text)
        except ValueError:
            data = {"body_md": text}
    return data


async def import_mcp(source: str) -> dict:
    server_url = os.environ.get("MCP_IMPORT_SERVER_URL", "").strip()
    tool_name = os.environ.get("MCP_IMPORT_TOOL", "import_source").strip()
    argument_name = os.environ.get("MCP_IMPORT_ARGUMENT", "source").strip()
    if not server_url:
        raise HTTPException(503, "尚未配置 MCP_IMPORT_SERVER_URL。")
    if not re.match(r"^https?://", server_url, re.I):
        raise HTTPException(503, "MCP 导入仅支持在本机 .env 中配置 Streamable HTTP 地址。")
    try:
        from mcp import Client
        async with asyncio.timeout(45):
            async with Client(server_url) as client:
                tools = await client.list_tools()
                if tool_name not in {tool.name for tool in tools.tools}:
                    raise HTTPException(503, f"MCP Server 没有提供工具 {tool_name}。")
                result = await client.call_tool(tool_name, {argument_name: source})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"MCP 导入失败：{type(exc).__name__}。请检查本机 MCP 配置和服务日志。") from exc
    if result.is_error:
        message = " ".join(getattr(block, "text", "") for block in result.content).strip()
        raise HTTPException(502, f"MCP 工具返回错误：{message or '未提供错误详情'}")
    data = _mcp_data(result)
    title = _clean(data.get("title")) or source
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    metadata = {**metadata, "import_provider": "mcp", "mcp_tool": tool_name}
    tags = data.get("tags") if isinstance(data.get("tags"), list) else ["MCP"]
    kind = data.get("kind") if data.get("kind") in {"concept", "resource", "repository", "model", "dataset", "benchmark", "experiment", "question", "task"} else "resource"
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    return _preview(
        source_type="mcp", source_key=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        source_url=data.get("source_url") or (source if re.match(r"^https?://", source, re.I) else None),
        title=title, summary=_clean(data.get("summary")), body_md=str(data.get("body_md") or ""),
        kind=kind, tags=[str(tag) for tag in tags], metadata=metadata,
        warnings=[str(item) for item in warnings],
    )


async def import_locator(source: str, source_type: str = "auto") -> dict:
    if not source.strip():
        raise HTTPException(422, "请输入资料地址或标识符。")
    selected = detect_source_type(source) if source_type == "auto" else source_type
    providers = {"arxiv": import_arxiv, "doi": import_doi, "github": import_github, "mcp": import_mcp}
    provider = providers.get(selected)
    if not provider:
        raise HTTPException(422, "不支持该资料来源。")
    return await provider(source.strip())
