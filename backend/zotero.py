"""Read-only adapter for kujenga/zotero-mcp over local stdio.

Only the server-side environment controls the executable. Browser requests can
search or select an item, but cannot supply a command or write to Zotero.
"""
import asyncio
from contextlib import asynccontextmanager
import json
import os
import re
import shutil

from fastapi import HTTPException
from mcp import Client, StdioServerParameters

from .importers import _preview

TOOLS = {'zotero_search_items', 'zotero_item_metadata', 'zotero_item_fulltext'}
DEFAULT_ARGS = ['zotero-mcp@0.3.1']


def configuration():
    enabled = os.environ.get('ZOTERO_MCP_ENABLED', '').lower() in ('true', '1', 'yes')
    command = os.environ.get('ZOTERO_MCP_COMMAND', 'uvx').strip()
    try:
        args = json.loads(os.environ.get('ZOTERO_MCP_ARGS', json.dumps(DEFAULT_ARGS)))
        if not command or not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError
    except (ValueError, TypeError):
        return enabled, None, 'Zotero MCP 配置无效，请检查后端启动命令和 JSON 参数列表。'
    executable = shutil.which(command)
    if not executable:
        return enabled, None, '找不到 Zotero MCP 启动程序，请安装 uv 或检查后端命令路径。'
    # Do not forward the workspace's LLM key, database password, or remote Zotero
    # credentials to the child process. The SDK supplies its basic system env.
    params = StdioServerParameters(command=executable, args=args, env={
        'ZOTERO_LOCAL': 'true', 'ZOTERO_LIBRARY_ID': '0', 'ZOTERO_LIBRARY_TYPE': 'user',
        'PYTHONIOENCODING': 'utf-8',
    })
    return enabled, params, None


def status():
    enabled, params, error = configuration()
    return {'enabled': enabled, 'configured': enabled and params is not None,
            'error': error if enabled else None}


@asynccontextmanager
async def connection():
    enabled, params, error = configuration()
    if not enabled:
        raise HTTPException(503, '本地 Zotero 接入未启用，请在后端设置 ZOTERO_MCP_ENABLED=true 并重启。')
    if error:
        raise HTTPException(503, error)
    try:
        async with asyncio.timeout(60):
            async with Client(params) as client:
                available = await client.list_tools()
                if not TOOLS.issubset({tool.name for tool in available.tools}):
                    raise HTTPException(503, 'Zotero MCP 工具不兼容，需要搜索、元数据和全文三个只读工具。')
                yield client
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(504, 'Zotero MCP 响应超时，请确认 Zotero 已打开后重试。') from None
    except Exception:
        raise HTTPException(502, '无法连接本地 Zotero MCP，请确认 Zotero 已打开并允许本机应用访问。') from None


def tool_text(result):
    if result.is_error:
        raise HTTPException(502, 'Zotero 工具调用失败，请检查本机 Zotero 和 MCP 服务。')
    data = result.structured_content
    if isinstance(data, dict):
        data = data.get('result')
    if isinstance(data, str):
        text = data
    else:
        text = '\n\n'.join(block.text for block in result.content if getattr(block, 'type', '') == 'text')
    text = text.strip()
    # kujenga/zotero-mcp reports certain failures as successful text responses.
    # Never mistake these for paper content or relay upstream exception details.
    if text.startswith('No item found with key:'):
        raise HTTPException(404, 'Zotero 条目不存在，请重新搜索后选择。')
    if text.startswith(('Error retrieving ', 'Error searching ')):
        raise HTTPException(502, 'Zotero 工具调用失败，请检查本机 Zotero 和 MCP 服务。')
    return text


def field(text, name):
    match = re.search(r'^' + re.escape(name) + r':\s*(.*)$', text, re.M)
    return match.group(1).strip().strip('`') if match else ''


def section(text, name):
    match = re.search(r'^### ' + re.escape(name) + r'\s*\n(.*?)(?=^#{1,3} |\Z)', text, re.M | re.S)
    return match.group(1).strip() if match else ''


def parse_search(text):
    if text.startswith('No items found matching your query.'):
        return []
    items = []
    seen = set()
    for match in re.finditer(r'^## \d+\. ([^\n]+)\n(.*?)(?=^## \d+\. |\Z)', text, re.M | re.S):
        title, body = match.groups()
        key = re.search(r'\*\*Key\*\*:\s*`([A-Z0-9]{8})`', body)
        if not key or key[1] in seen:
            continue
        seen.add(key[1])
        def value(label):
            found = re.search(r'\*\*' + label + r'\*\*:\s*([^\n|]*)', body)
            return found[1].strip() if found else ''
        authors = value('Authors')
        items.append({'item_key': key[1], 'title': title.strip(), 'authors': '' if authors == 'No authors' else authors,
                      'date': value('Date'), 'item_type': value('Type')})
    if not items:
        raise HTTPException(502, '无法解析 Zotero 搜索结果，请使用兼容的 kujenga/zotero-mcp 版本。')
    return items


async def search(query, qmode='titleCreatorYear', tag='', limit=20):
    if not query.strip():
        raise HTTPException(422, '请输入 Zotero 搜索词。')
    async with connection() as client:
        args = {'query': query.strip(), 'qmode': qmode, 'limit': limit}
        if tag.strip():
            args['tag'] = tag.strip()
        text = tool_text(await client.call_tool('zotero_search_items', args))
    items = parse_search(text)
    # Do not claim exhaustion: this tool caps matches, then groups child hits.
    return {'items': items, 'limit': limit}


async def preview(item_key, include_fulltext=True):
    if not re.fullmatch(r'[A-Z0-9]{8}', item_key):
        raise HTTPException(422, 'Zotero 条目 Key 必须是 8 位大写字母或数字。')
    warnings = []
    fulltext = ''
    async with connection() as client:
        metadata_md = tool_text(await client.call_tool('zotero_item_metadata', {'item_key': item_key}))
        title_match = re.search(r'^## (.+)$', metadata_md, re.M)
        if not title_match or field(metadata_md, 'Item Key') != item_key:
            raise HTTPException(502, '无法解析 Zotero 条目元数据，请重新搜索或检查 MCP 版本。')
        if include_fulltext:
            try:
                fulltext_md = tool_text(await client.call_tool('zotero_item_fulltext', {'item_key': item_key}))
                content = re.search(r'^## Document Content\s*\n(.*)\Z', fulltext_md, re.M | re.S)
                if content and content[1].strip() and not content[1].lstrip().startswith('[⚠'):
                    fulltext = content[1].strip()
                else:
                    warnings.append('未读取到 Zotero 全文；请检查附件是否已下载并完成全文索引。当前预览保留元数据。')
            except HTTPException:
                warnings.append('Zotero 全文读取失败，当前预览仅包含元数据，可继续确认导入或稍后重试。')
    tags = re.findall(r'`([^`]+)`', section(metadata_md, 'Tags'))
    authors = field(metadata_md, 'Authors') or field(metadata_md, 'Author')
    metadata = {'subtype': 'paper', 'import_provider': 'zotero', 'zotero_item_key': item_key,
                'zotero_library': 'local:0', 'zotero_uri': f'zotero://select/library/items/{item_key}',
                'authors': authors, 'date': field(metadata_md, 'Date'),
                'doi': field(metadata_md, 'DOI'), 'citation_key': field(metadata_md, 'Citation Key'),
                'item_type': field(metadata_md, 'Type'), 'fulltext_included': bool(fulltext)}
    # Keep the existing API/database source_type identifier. Namespace the key
    # so Zotero items cannot collide with other MCP imports; no schema change.
    return _preview(source_type='mcp', source_key=f'zotero:local:0:{item_key}',
                    source_url=field(metadata_md, 'URL') or (f'https://doi.org/{metadata["doi"]}' if metadata['doi'] else None),
                    title=title_match[1].strip(), summary=section(metadata_md, 'Abstract'),
                    body_md=metadata_md + (f'\n\n## Document Content\n\n{fulltext}' if fulltext else ''),
                    tags=tags, metadata=metadata, warnings=warnings)
