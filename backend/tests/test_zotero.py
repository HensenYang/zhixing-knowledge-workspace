"""Zotero adapter contracts: fake stdio client, no personal database or library."""
import asyncio
import json
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

import backend.app as workspace
from backend import zotero

KEY = 'ABCD1234'
METADATA = f'''## 原始论文标题
Item Key: `{KEY}`
Citation Key: `Author2026`
Type: journalArticle
Date: 2026
Authors: Wang, A; Li, B

### Abstract
原始摘要，不随界面语言变化。

### Tags
`机器人`, `Original tag`

### Identifiers
DOI: 10.1234/paper
URL: https://example.org/paper
'''
SEARCH = f'''# Search Results for: 'robot'
Found 1 items across 2 matches, all of which were inside attachments or notes.

## 1. 原始论文标题
**Type**: journalArticle | **Date**: 2026 | **Key**: `{KEY}` | **Citation Key**: `Author2026`
**Authors**: Wang, A; Li, B
'''


def result(text='', *, error=False, structured=False):
    return SimpleNamespace(is_error=error, structured_content={'result': text} if structured else None,
                           content=[SimpleNamespace(type='text', text=text)])


@pytest.fixture(autouse=True)
def config(monkeypatch):
    for name in ('ZOTERO_MCP_ENABLED', 'ZOTERO_MCP_COMMAND', 'ZOTERO_MCP_ARGS'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('ZOTERO_MCP_ENABLED', 'true')
    monkeypatch.setattr(zotero.shutil, 'which', lambda name: 'C:/tools/uvx.exe')


@pytest.fixture
def fake_client(monkeypatch):
    state = SimpleNamespace(calls=[], params=None, tools=zotero.TOOLS.copy(),
                            search=SEARCH, metadata=METADATA,
                            fulltext=METADATA + '\n## Document Content\n\nOriginal full text. 原文。',
                            fulltext_error=False, fail=None)

    class FakeClient:
        def __init__(self, params):
            state.params = params

        async def __aenter__(self):
            if state.fail:
                raise state.fail
            return self

        async def __aexit__(self, *args):
            return False

        async def list_tools(self):
            return SimpleNamespace(tools=[SimpleNamespace(name=name) for name in state.tools])

        async def call_tool(self, name, args):
            state.calls.append((name, args))
            text = {'zotero_search_items': state.search, 'zotero_item_metadata': state.metadata,
                    'zotero_item_fulltext': state.fulltext}[name]
            return result(text, error=name == 'zotero_item_fulltext' and state.fulltext_error, structured=True)

    monkeypatch.setattr(zotero, 'Client', FakeClient)
    return state


def test_stdio_config_is_local_and_does_not_forward_workspace_secrets(monkeypatch, fake_client):
    monkeypatch.setenv('LLM_API_KEY', 'never-forward-this')
    monkeypatch.setenv('DATABASE_URL', 'never-forward-this-either')
    monkeypatch.setenv('ZOTERO_API_KEY', 'remote-key-not-forwarded')
    monkeypatch.setenv('ZOTERO_MCP_ARGS', json.dumps(['--offline', 'zotero-mcp@0.3.1']))
    found = asyncio.run(zotero.search(' robot ', 'everything', ' 用户标签 ', 50))
    assert found['items'][0]['item_key'] == KEY
    assert fake_client.calls == [('zotero_search_items', {'query': 'robot', 'qmode': 'everything', 'tag': '用户标签', 'limit': 50})]
    assert fake_client.params.args == ['--offline', 'zotero-mcp@0.3.1']
    assert fake_client.params.env['ZOTERO_LOCAL'] == 'true'
    assert fake_client.params.env['ZOTERO_LIBRARY_ID'] == '0'
    assert not {'LLM_API_KEY', 'DATABASE_URL', 'ZOTERO_API_KEY'} & fake_client.params.env.keys()


def test_preview_maps_metadata_fulltext_and_stable_source_key(fake_client):
    preview = asyncio.run(zotero.preview(KEY))
    assert preview['title'] == '原始论文标题'
    assert preview['summary'] == '原始摘要，不随界面语言变化。'
    assert preview['source_type'] == 'mcp'
    assert preview['source_key'] == 'zotero:local:0:ABCD1234'
    assert preview['source_url'] == 'https://example.org/paper'
    assert preview['tags'] == ['Original tag', '机器人']
    assert preview['metadata']['citation_key'] == 'Author2026'
    assert preview['metadata']['doi'] == '10.1234/paper'
    assert preview['metadata']['fulltext_included'] is True
    assert 'Original full text. 原文。' in preview['body_md']
    assert preview['body_md'].count('## 原始论文标题') == 1
    assert preview['warnings'] == []


def test_metadata_only_never_calls_fulltext(fake_client):
    preview = asyncio.run(zotero.preview(KEY, False))
    assert [name for name, _ in fake_client.calls] == ['zotero_item_metadata']
    assert preview['metadata']['fulltext_included'] is False
    assert preview['warnings'] == []


@pytest.mark.parametrize('text', [METADATA + '\n## Attachment Information\n[❌ No suitable attachment found]',
                                 METADATA + '\n## Document Content\n\n[⚠️ Attachment is available but text extraction is not possible.]',
                                 'Error retrieving item full text: local failure'])
def test_missing_or_failed_fulltext_keeps_metadata_with_warning(fake_client, text):
    fake_client.fulltext = text
    preview = asyncio.run(zotero.preview(KEY))
    assert preview['title'] == '原始论文标题'
    assert preview['metadata']['fulltext_included'] is False
    assert len(preview['warnings']) == 1
    assert 'local failure' not in preview['body_md']


def test_tool_error_retains_metadata(fake_client):
    fake_client.fulltext_error = True
    assert asyncio.run(zotero.preview(KEY))['warnings']


@pytest.mark.parametrize('text,status', [('No item found with key: ABCD1234', 404), ('Error retrieving item metadata: secret', 502), ('unsupported metadata format', 502)])
def test_bad_metadata_cannot_be_imported(fake_client, text, status):
    fake_client.metadata = text
    with pytest.raises(HTTPException) as error:
        asyncio.run(zotero.preview(KEY))
    assert error.value.status_code == status
    assert 'secret' not in error.value.detail
    assert len(fake_client.calls) == 1


def test_search_empty_and_malformed_results_are_distinct(fake_client):
    fake_client.search = 'No items found matching your query.'
    assert asyncio.run(zotero.search('none'))['items'] == []
    fake_client.search = 'unknown protocol output'
    with pytest.raises(HTTPException) as error:
        asyncio.run(zotero.search('none'))
    assert error.value.status_code == 502


def test_search_multiple_items_preserves_titles_and_distinct_keys():
    text = SEARCH + '\n\n## 2. Another paper\n**Type**: preprint | **Date**: 2025 | **Key**: `EFGH5678`\n**Authors**: No authors\n'
    items = zotero.parse_search(text)
    assert [item['title'] for item in items] == ['原始论文标题', 'Another paper']
    assert [item['item_key'] for item in items] == [KEY, 'EFGH5678']
    assert items[1]['authors'] == ''


@pytest.mark.parametrize('setting,value', [('ZOTERO_MCP_ENABLED', 'false'), ('ZOTERO_MCP_ARGS', 'not-json'), ('ZOTERO_MCP_ARGS', '{"shell":"anything"}')])
def test_disabled_or_invalid_configuration_does_not_launch_client(monkeypatch, fake_client, setting, value):
    monkeypatch.setenv(setting, value)
    with pytest.raises(HTTPException) as error:
        asyncio.run(zotero.search('robot'))
    assert error.value.status_code == 503
    assert fake_client.params is None


def test_missing_executable_and_missing_tools(monkeypatch, fake_client):
    monkeypatch.setattr(zotero.shutil, 'which', lambda name: None)
    assert zotero.status()['configured'] is False
    monkeypatch.setattr(zotero.shutil, 'which', lambda name: 'uvx')
    fake_client.tools = {'zotero_search_items'}
    with pytest.raises(HTTPException) as error:
        asyncio.run(zotero.search('robot'))
    assert error.value.status_code == 503


@pytest.mark.parametrize('failure,status', [(TimeoutError(), 504), (RuntimeError('secret'), 502)])
def test_transport_failures_are_safe(fake_client, failure, status):
    fake_client.fail = failure
    with pytest.raises(HTTPException) as error:
        asyncio.run(zotero.search('robot'))
    assert error.value.status_code == status
    assert 'secret' not in error.value.detail


def test_search_and_preview_api_never_write_database(monkeypatch, fake_client):
    async def no_pdf(data, *args):
        return data
    def no_database():
        raise AssertionError('Search must not access the database')
    monkeypatch.setattr(workspace, 'db', no_database)
    monkeypatch.setattr(workspace.import_assets, 'zotero_pdf', no_pdf)
    monkeypatch.setattr(workspace, 'add_duplicate_hints', lambda data: {**data, 'possible_duplicates': []})
    with TestClient(workspace.app) as client:
        assert client.get('/api/source-imports/providers').json()['zotero']['configured'] is True
        assert client.post('/api/source-imports/zotero/search', json={'query': 'robot'}).json()['items'][0]['item_key'] == KEY
        response = client.post('/api/source-imports/zotero/preview', json={'item_key': KEY})
        assert response.status_code == 200
        assert response.json()['possible_duplicates'] == []
        assert client.post('/api/source-imports/zotero/search', json={'query': 'robot', 'limit': 101}).status_code == 422
        assert client.post('/api/source-imports/zotero/search', json={'query': 'robot', 'qmode': 'anything'}).status_code == 422
        assert client.post('/api/source-imports/zotero/preview', json={'item_key': 'not-a-key'}).status_code == 422
