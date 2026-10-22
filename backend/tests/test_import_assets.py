import asyncio
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time
from uuid import UUID, uuid4

from fastapi import HTTPException
import httpx
from PIL import Image
import pymupdf
import pytest

import backend.app as workspace
from backend import import_assets as media


def pdf_bytes(vector=True, text=True):
    image = io.BytesIO()
    Image.new('RGB', (60, 40), '#39a878').save(image, 'PNG')
    document = pymupdf.open()
    page = document.new_page(width=300, height=400)
    if text:
        page.insert_text((20, 30), 'A paper with a figure.')
    page.insert_image(pymupdf.Rect(20, 50, 180, 150), stream=image.getvalue())
    if vector:
        page.draw_rect(pymupdf.Rect(30, 180, 230, 280), color=(0.3, 0.4, 0.6))
    return document.tobytes()


def test_pdf_preview_extracts_raster_and_preserves_vector_page_without_database(tmp_path):
    preview = media.local_pdf(pdf_bytes(), 'paper.pdf', tmp_path)
    assert {asset['kind'] for asset in preview['assets']} == {'source', 'image', 'page'}
    assert preview['metadata']['image_count'] == 2
    assert 'A paper with a figure.' in preview['body_md']
    assert 'import-asset://' in preview['body_md']
    assert not (tmp_path / 'attachments').exists()
    for asset in preview['assets']:
        path, _ = media.asset_file(tmp_path, preview['preview_token'], asset['id'])
        assert path.read_bytes().startswith(b'%PDF' if asset['kind'] == 'source' else b'\x89PNG')


def test_scanned_pdf_still_has_image_references_without_ocr(tmp_path):
    preview = media.local_pdf(pdf_bytes(vector=False, text=False), 'scan.pdf', tmp_path)
    assert 'import-asset://' in preview['body_md']
    assert any('OCR' in warning for warning in preview['warnings'])


def test_failed_image_parser_keeps_readable_text_and_original_pdf(monkeypatch, tmp_path):
    content = pdf_bytes()
    def broken_renderer(*args, **kwargs):
        raise RuntimeError('cannot render this PDF')
    monkeypatch.setattr(media.pymupdf, 'open', broken_renderer)
    preview = media.local_pdf(content, 'paper.pdf', tmp_path)
    assert 'A paper with a figure.' in preview['body_md']
    assert len(preview['assets']) == 1 and preview['assets'][0]['kind'] == 'source'
    assert preview['warnings']


def test_assets_promote_to_stable_local_attachment_references(tmp_path):
    preview = media.local_pdf(pdf_bytes(), 'paper.pdf', tmp_path)
    written = []
    with media.claim(tmp_path, preview['preview_token'], preview['source_type'], preview['source_key']) as manifest:
        body = media.resolve_body(preview['body_md'], manifest)
        assets = media.persist(tmp_path, preview['preview_token'], manifest, written)
        assert 'import-asset://' not in body
        assert all((tmp_path / 'attachments' / item['id']).exists() for item in assets)
        for item in assets:
            if item['kind'] != 'source':
                assert f'/api/attachments/{item["id"]}/content' in body
        with pytest.raises(HTTPException) as error:
            with media.claim(tmp_path, preview['preview_token'], preview['source_type'], preview['source_key']):
                pass
        assert error.value.status_code == 409
    media.discard(tmp_path, preview['preview_token'])
    assert all(path.exists() for path in written)
    with pytest.raises(HTTPException):
        media.load(tmp_path, preview['preview_token'])


def test_expired_mismatched_and_tampered_previews_are_rejected(tmp_path):
    preview = media.local_pdf(pdf_bytes(), 'paper.pdf', tmp_path)
    token = preview['preview_token']
    with pytest.raises(HTTPException):
        with media.claim(tmp_path, token, 'mcp', 'another-source'):
            pass
    with pytest.raises(HTTPException):
        media.resolve_body(f'![x](import-asset://{uuid4()})', None)
    directory, manifest = media.load(tmp_path, token)
    (directory / manifest['assets'][0]['id']).write_bytes(b'tampered')
    with pytest.raises(HTTPException):
        media.persist(tmp_path, token, manifest, [])
    old = time.time() - media.TTL - 1
    os.utime(directory, (old, old))
    with pytest.raises(HTTPException):
        media.load(tmp_path, token)
    media.cleanup(tmp_path)
    assert not directory.exists()


@pytest.mark.parametrize('token', ['../attachments', 'a/b', 'a'*31, 'a'*33])
def test_preview_paths_cannot_escape_staging_root(tmp_path, token):
    with pytest.raises(HTTPException):
        media.asset_file(tmp_path, token, '../anything')


@pytest.mark.parametrize('fail_commit', [False, True])
def test_confirmation_saves_files_with_transaction_and_cleans_up_on_failure(monkeypatch, tmp_path, fail_commit):
    preview = media.local_pdf(pdf_bytes(), 'paper.pdf', tmp_path)
    state = SimpleNamespace(sql='', body=None, attachments=[], row={'id': str(uuid4()), 'title': preview['title']})
    class Cursor:
        def execute(self, sql, args=()):
            state.sql = sql
            if sql.startswith('INSERT INTO objects'):
                state.body = args[3]
            if sql.startswith('INSERT INTO attachments'):
                state.attachments.append(args)
        def fetchone(self):
            return None if state.sql.startswith('SELECT s.object_id') else state.row
    @contextmanager
    def fake_db():
        yield Cursor()
        if fail_commit:
            raise RuntimeError('simulated commit failure')
    monkeypatch.setattr(workspace, 'STORAGE', tmp_path)
    monkeypatch.setattr(workspace, 'db', fake_db)
    monkeypatch.setattr(workspace, 'set_tags', lambda *args: None)
    monkeypatch.setattr(workspace, 'object_with_tags', lambda cursor, row: row)
    payload = workspace.SourceImportCommit(source_type='pdf', source_key=preview['source_key'], preview_token=preview['preview_token'], object={'kind':'resource','title':preview['title'],'body_md':preview['body_md']})
    if fail_commit:
        with pytest.raises(RuntimeError):
            workspace.commit_source_import(payload)
        assert not list((tmp_path / 'attachments').iterdir())
        assert media.load(tmp_path, preview['preview_token'])
    else:
        workspace.commit_source_import(payload)
        assert len(state.attachments) == 3
        assert '/api/attachments/' in state.body and 'import-asset://' not in state.body
        assert len(list((tmp_path / 'attachments').iterdir())) == 3


def test_preview_asset_endpoint_is_inline_and_does_not_write_notes(monkeypatch, tmp_path):
    monkeypatch.setattr(workspace, 'STORAGE', tmp_path)
    preview = media.local_pdf(pdf_bytes(), 'paper.pdf', tmp_path)
    image = next(item for item in preview['assets'] if item['kind'] == 'image')
    response = workspace.preview_import_asset(preview['preview_token'], UUID(image['id']))
    assert response.status_code == 200
    assert Path(response.path).read_bytes().startswith(b'\x89PNG')
    assert response.headers['content-disposition'].startswith('inline')
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert not (tmp_path/'attachments').exists()


def test_zotero_local_file_redirect_copies_pdf_images_and_handles_percent_names(monkeypatch, tmp_path):
    pdf = tmp_path / 'paper %20 original.pdf'
    pdf.write_bytes(pdf_bytes())
    def handler(request):
        if request.url.path.endswith('/children'):
            return httpx.Response(200, json=[{'data':{'key':'PDFD1234','contentType':'application/pdf','md5':'a'}}])
        if request.url.path.endswith('/file'):
            return httpx.Response(302, headers={'location': pdf.as_uri()})
        return httpx.Response(200, json={'data':{'itemType':'journalArticle'}})
    real = httpx.AsyncClient
    monkeypatch.setattr(media.httpx, 'AsyncClient', lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    preview = {'source_type':'mcp','source_key':'zotero:local:0:ABCD1234','body_md':'Original indexed text','metadata':{},'warnings':[]}
    result = asyncio.run(media.zotero_pdf(preview, 'ABCD1234', tmp_path))
    assert result['metadata']['zotero_attachment_key'] == 'PDFD1234'
    assert result['body_md'].startswith('Original indexed text')
    assert len(result['assets']) == 3
    assert result['assets'][0]['filename'] == pdf.name


def test_zotero_rejects_network_file_redirect_and_keeps_text(monkeypatch, tmp_path):
    def handler(request):
        if request.url.path.endswith('/file'):
            return httpx.Response(302, headers={'location':'https://example.org/private.pdf'})
        return httpx.Response(200, json={'data':{'key':'PDFD1234','itemType':'attachment','contentType':'application/pdf'}})
    real = httpx.AsyncClient
    monkeypatch.setattr(media.httpx, 'AsyncClient', lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    preview = {'body_md':'Original text','metadata':{},'warnings':[]}
    result = asyncio.run(media.zotero_pdf(preview, 'ABCD1234', tmp_path))
    assert result['body_md'] == 'Original text'
    assert len(result['warnings']) == 1 and 'assets' not in result
