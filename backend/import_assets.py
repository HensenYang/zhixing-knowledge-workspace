"""Temporary PDF import assets, promoted to real attachments only on confirmation."""
from contextlib import contextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import time
from urllib.parse import urlsplit
from urllib.request import url2pathname
from uuid import uuid4

from fastapi import HTTPException
import httpx
import pymupdf

from .importers import import_pdf, MAX_PDF_BYTES

TTL = 2 * 60 * 60
MAX_IMAGES = 80
MAX_ASSET_BYTES = 72 * 1024 * 1024
TOKEN = re.compile(r'^[A-Za-z0-9_-]{32}$')
ASSET_REF = re.compile(r'import-asset://([a-f0-9-]{36})')


def root(storage):
    directory = Path(storage).resolve() / 'import-previews'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def discard(storage, token):
    if not TOKEN.fullmatch(token):
        return
    directory = root(storage) / token
    if directory.resolve().is_relative_to(root(storage)) and not directory.is_symlink():
        shutil.rmtree(directory, ignore_errors=True)


def cleanup(storage):
    for directory in list(root(storage).iterdir())[:256]:
        if TOKEN.fullmatch(directory.name) and directory.is_dir() and not (directory / '.lock').exists():
            if time.time() - directory.stat().st_mtime > TTL:
                discard(storage, directory.name)


def load(storage, token):
    if not TOKEN.fullmatch(token):
        raise HTTPException(404, '导入预览不存在或已过期，请重新提取资料。')
    directory = root(storage) / token
    try:
        if directory.is_symlink() or time.time() - directory.stat().st_mtime > TTL:
            raise ValueError
        return directory, json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise HTTPException(404, '导入预览不存在或已过期，请重新提取资料。') from None


def asset_file(storage, token, asset_id):
    directory, manifest = load(storage, token)
    asset = next((item for item in manifest['assets'] if item['id'] == asset_id), None)
    if asset is None:
        raise HTTPException(404, '导入图片或附件不存在，请重新提取资料。')
    return directory / asset['id'], asset


@contextmanager
def claim(storage, token, source_type, source_key):
    if token is None:
        yield None
        return
    directory, manifest = load(storage, token)
    if manifest['source_type'] != source_type or manifest['source_key'] != source_key:
        raise HTTPException(409, '导入来源与附件预览不一致，请重新提取资料。')
    try:
        lock = (directory / '.lock').open('x')
    except FileExistsError:
        raise HTTPException(409, '此导入正在保存，请等待完成后再操作。') from None
    try:
        with lock:
            yield manifest
    finally:
        (directory / '.lock').unlink(missing_ok=True)


def resolve_body(body, manifest):
    allowed = {item['id'] for item in manifest['assets']} if manifest else set()
    def replace(match):
        if match[1] not in allowed:
            raise HTTPException(409, '正文中的图片引用与预览不一致，请重新提取资料。')
        return f'/api/attachments/{match[1]}/content'
    body = ASSET_REF.sub(replace, body)
    if 'import-asset://' in body:
        raise HTTPException(409, '正文中的图片引用与预览不一致，请重新提取资料。')
    return body


def persist(storage, token, manifest, written):
    if manifest is None:
        return []
    directory, _ = load(storage, token)
    target = Path(storage) / 'attachments'
    target.mkdir(parents=True, exist_ok=True)
    for asset in manifest['assets']:
        source = directory / asset['id']
        if not source.is_file() or source.stat().st_size != asset['size_bytes']:
            raise HTTPException(409, '导入附件校验失败，请重新提取资料。')
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != asset['sha256']:
            raise HTTPException(409, '导入附件校验失败，请重新提取资料。')
        path = target / asset['id']
        with path.open('xb') as output:
            written.append(path)
            output.write(content)
    return manifest['assets']


def pdf_assets(content, filename, preview, storage):
    """Raster crops plus page previews for vector graphics; never perform OCR."""
    if len(content) > MAX_PDF_BYTES or not content.startswith(b'%PDF'):
        raise HTTPException(422, '无法读取本地 PDF 附件，请检查文件格式和大小。')
    cleanup(storage)
    token = secrets.token_urlsafe(24)
    directory = root(storage) / token
    directory.mkdir()
    assets, page_refs, hashes = [], {}, {}
    total_bytes = len(content)
    limited = False
    def store(data, name, mime, kind, page=None):
        digest = hashlib.sha256(data).hexdigest()
        if digest in hashes:
            return hashes[digest]
        asset_id = str(uuid4())
        (directory / asset_id).write_bytes(data)
        asset = {'id': asset_id, 'filename': name, 'mime_type': mime, 'kind': kind,
                 'page': page, 'size_bytes': len(data), 'sha256': digest}
        assets.append(asset); hashes[digest] = asset
        return asset
    try:
        store(content, Path(filename).name, 'application/pdf', 'source')
        try:
            document = pymupdf.open(stream=content, filetype='pdf')
        except (RuntimeError, ValueError):
            document = None
            preview['warnings'].append('PDF 图片解析失败，已保留正文和原始 PDF。')
        with document if document is not None else nullcontext() as document:
            if document is not None and document.needs_pass:
                raise HTTPException(422, '暂不支持加密 PDF。')
            for index in range(min(len(document), 200) if document is not None else 0):
                page = document[index]
                try:
                    boxes = []
                    for info in page.get_image_info():
                        box = pymupdf.Rect(info['bbox']) & page.rect
                        if box.width >= 12 and box.height >= 12 and tuple(box) not in [tuple(item[0]) for item in boxes]:
                            boxes.append((box, 'image'))
                    # A vector chart cannot be recovered as an embedded raster.
                    # Preserve its page appearance explicitly instead of claiming
                    # to identify or crop the paper's semantic figure boundaries.
                    if page.get_drawings():
                        boxes.append((page.rect, 'page'))
                    for image_index, (box, kind) in enumerate(boxes, 1):
                        if len(assets) - 1 >= MAX_IMAGES:
                            limited = True; break
                        scale = min(2, 1800 / max(box.width, box.height))
                        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=box, alpha=False)
                        data = pixmap.tobytes('png')
                        if total_bytes + len(data) > MAX_ASSET_BYTES:
                            limited = True; continue
                        before = len(assets)
                        asset = store(data, f'page-{index+1}-{kind}-{image_index}.png', 'image/png', kind, index + 1)
                        if len(assets) > before:
                            total_bytes += len(data)
                        label = f'Page {index+1} {kind} {image_index} / 第 {index+1} 页'
                        page_refs.setdefault(index+1, []).append(f'![{label}](import-asset://{asset["id"]})')
                except Exception:
                    preview['warnings'].append(f'第 {index+1} 页图片提取失败，已保留原始 PDF。')
                if limited and len(assets)-1 >= MAX_IMAGES:
                    break
            if document is not None and len(document) > 200:
                limited = True
        if limited:
            preview['warnings'].append('图片提取达到数量或大小上限，部分图片未提取；完整内容仍保留在原始 PDF 中。')
        # Put local-PDF image references beneath their actual page, including
        # pages with no text layer. Zotero's indexed text has no reliable page
        # boundaries, so give those assets explicit page-labelled sections.
        if preview['source_type'] == 'pdf':
            existing = {int(match[1]): match[2].strip() for match in re.finditer(r'^## 第 (\d+) 页\n(.*?)(?=^## 第 \d+ 页\n|\Z)', preview['body_md'], re.M | re.S)}
            preview['body_md'] = '\n\n'.join(f'## 第 {number} 页\n\n' + '\n\n'.join(filter(None, [existing.get(number, ''), *page_refs.get(number, [])])) for number in sorted(set(existing) | set(page_refs)))
        elif page_refs:
            preview['body_md'] += '\n\n' + '\n\n'.join(f'## PDF page {number} / PDF 第 {number} 页\n\n' + '\n\n'.join(refs) for number, refs in page_refs.items())
        manifest = {'source_type': preview['source_type'], 'source_key': preview['source_key'], 'assets': assets}
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
        preview['preview_token'] = token
        preview['assets'] = [{**item, 'preview_url': f'/api/source-imports/assets/{token}/{item["id"]}'} for item in assets]
        preview['metadata']['image_count'] = len(assets)-1
        preview['metadata']['pdf_sha256'] = hashlib.sha256(content).hexdigest()
        return preview
    except Exception:
        discard(storage, token)
        raise


def local_pdf(content, filename, storage):
    return pdf_assets(content, filename, import_pdf(content, filename), storage)


async def zotero_pdf(preview, item_key, storage):
    """Read an attachment via Zotero's fixed localhost API, not a browser path."""
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=15, follow_redirects=False) as client:
            base = 'http://127.0.0.1:23119/api/users/0/items/'
            item = await client.get(base + item_key)
            item.raise_for_status()
            data = item.json().get('data', {})
            if data.get('itemType') == 'attachment':
                candidates = [item.json()]
            else:
                children = await client.get(base + item_key + '/children')
                children.raise_for_status()
                candidates = children.json()
            candidates = [item['data'] for item in candidates if item.get('data', {}).get('contentType') == 'application/pdf']
            if not candidates:
                raise ValueError
            # Keep the same deterministic PDF choice as the installed MCP.
            data = sorted(candidates, key=lambda item: item.get('md5', ''), reverse=True)[0]
            key = data.get('key', '')
            if not re.fullmatch(r'[A-Z0-9]{8}', key):
                raise ValueError
            response = await client.get(base + key + '/file')
            if response.status_code == 302:
                url = urlsplit(response.headers.get('location', ''))
                # Zotero itself resolves stored or linked files. No path is
                # accepted from browser input; never follow network redirects.
                if url.scheme != 'file' or url.netloc not in ('', 'localhost'):
                    raise ValueError
                path = Path(url2pathname(url.path))
                if not path.is_file() or path.suffix.lower() != '.pdf' or path.stat().st_size > MAX_PDF_BYTES:
                    raise ValueError
                content = path.read_bytes()
                filename = path.name
            elif response.status_code == 200:
                content = response.content
                filename = data.get('filename') or f'{key}.pdf'
            else:
                raise ValueError
        preview = pdf_assets(content, filename, preview, storage)
        preview['metadata']['zotero_attachment_key'] = key
    except (OSError, ValueError, httpx.HTTPError, HTTPException):
        preview['warnings'].append('无法读取 Zotero 原始 PDF，当前预览保留文本；请确认附件已下载且本机可访问。')
    return preview
