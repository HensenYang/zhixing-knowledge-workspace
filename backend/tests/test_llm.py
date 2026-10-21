"""LLM contract tests: no external API calls and no database required."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend import llm

REAL_ASYNC_CLIENT = httpx.AsyncClient
KEY = 'test-only-secret-never-return'
ENV_NAMES = ('LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL', 'LLM_TIMEOUT_SECONDS',
             'LLM_MAX_OUTPUT_TOKENS', 'LLM_TOKEN_PARAMETER')


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def configured(monkeypatch):
    for name, value in {'LLM_API_KEY': KEY, 'LLM_BASE_URL': 'https://provider.example/v1/',
                        'LLM_MODEL': 'team-model'}.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def client():
    # Exercise the model router contract without application auth/database middleware.
    # Authenticated application access is covered by test_workspace.py.
    app = FastAPI()
    app.include_router(llm.router)
    with TestClient(app) as client:
        yield client


def mock_provider(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(llm.httpx, 'AsyncClient', lambda **kwargs: REAL_ASYNC_CLIENT(transport=transport, **kwargs))


def successful_reply():
    return {'choices': [{'message': {'content': 'OK'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 8, 'completion_tokens': 1, 'total_tokens': 9, 'private': KEY}}


def test_status_is_local_and_unconfigured_requests_fail(client, monkeypatch):
    def unexpected_client(**kwargs):
        pytest.fail('Unconfigured requests must not call a provider')
    monkeypatch.setattr(llm.httpx, 'AsyncClient', unexpected_client)
    result = client.get('/api/llm/status').json()
    assert result['configured'] is False
    assert result['missing'] == ['LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL']
    assert client.post('/api/llm/test').status_code == 503
    assert client.post('/api/llm/chat', json={'messages': [{'role': 'user', 'content': 'Hi'}]}).status_code == 503


def test_status_never_returns_key(client, configured):
    response = client.get('/api/llm/status')
    assert response.json()['configured'] is True
    assert response.json()['base_url'] == 'https://provider.example/v1'
    assert response.json()['model'] == 'team-model'
    assert KEY not in response.text
    assert KEY not in repr(llm.require_configuration())


@pytest.mark.parametrize('name,value', [
    ('LLM_BASE_URL', 'http://provider.example/v1'),
    ('LLM_BASE_URL', 'https://user:secret@provider.example/v1'),
    ('LLM_BASE_URL', 'https://provider.example/v1?api_key=secret'),
    ('LLM_BASE_URL', 'https://provider.example:bad/v1'),
    ('LLM_TIMEOUT_SECONDS', 'infinity'), ('LLM_TIMEOUT_SECONDS', '121'),
    ('LLM_MAX_OUTPUT_TOKENS', '0'), ('LLM_TOKEN_PARAMETER', 'invalid'),
    ('LLM_API_KEY', 'unsafe\nheader'),
    ('LLM_API_KEY', '非ASCII密钥'),
])
def test_invalid_configuration_is_reported_safely(client, configured, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    result = client.get('/api/llm/status')
    assert result.json()['configured'] is False
    assert result.json()['error']
    assert result.json()['base_url'] is None
    assert KEY not in result.text
    assert client.post('/api/llm/test').status_code == 503


def test_chat_sends_server_credentials_and_returns_normalized_text(client, configured, monkeypatch):
    messages = [{'role': 'user', 'content': '解释一下知识图谱'}]
    def handler(request):
        assert str(request.url) == 'https://provider.example/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer ' + KEY
        assert json.loads(request.content) == {'model': 'team-model', 'messages': messages,
                                                'stream': False, 'max_completion_tokens': 1024}
        return httpx.Response(200, json=successful_reply())
    mock_provider(monkeypatch, handler)
    response = client.post('/api/llm/chat', json={'messages': messages})
    assert response.status_code == 200
    assert response.json() == {'model': 'team-model', 'content': 'OK', 'finish_reason': 'stop',
                                'usage': {'prompt_tokens': 8, 'completion_tokens': 1, 'total_tokens': 9}}
    assert KEY not in response.text


def test_connection_test_uses_only_fixed_prompt_and_supports_local_provider(client, configured, monkeypatch):
    monkeypatch.setenv('LLM_BASE_URL', 'http://127.0.0.1:1234/v1')
    monkeypatch.setenv('LLM_TOKEN_PARAMETER', 'max_tokens')
    def handler(request):
        payload = json.loads(request.content)
        assert payload['messages'] == [{'role': 'user', 'content': 'Reply with OK.'}]
        assert payload['max_tokens'] == 1024
        assert 'max_completion_tokens' not in payload
        return httpx.Response(200, json=successful_reply())
    mock_provider(monkeypatch, handler)
    response = client.post('/api/llm/test')
    assert response.status_code == 200
    assert response.json()['ok'] is True


@pytest.mark.parametrize('status,expected', [(401, 502), (403, 502), (429, 429), (400, 502), (500, 502), (302, 502)])
def test_provider_errors_are_redacted(client, configured, monkeypatch, status, expected):
    mock_provider(monkeypatch, lambda request: httpx.Response(status, text=KEY))
    response = client.post('/api/llm/test')
    assert response.status_code == expected
    assert KEY not in response.text


@pytest.mark.parametrize('error,expected', [(httpx.ReadTimeout, 504), (httpx.ConnectError, 502)])
def test_network_errors_are_redacted(client, configured, monkeypatch, error, expected):
    def handler(request):
        raise error(KEY, request=request)
    mock_provider(monkeypatch, handler)
    response = client.post('/api/llm/test')
    assert response.status_code == expected
    assert KEY not in response.text


@pytest.mark.parametrize('body', [None, {}, {'choices': []}, {'choices': [{'message': {'content': None}}]},
                                 {'choices': [{'message': {'content': ' '}}]}, ['bad response']])
def test_invalid_provider_response_fails_cleanly(client, configured, monkeypatch, body):
    mock_provider(monkeypatch, lambda request: httpx.Response(200, content=json.dumps(body)))
    response = client.post('/api/llm/test')
    assert response.status_code == 502


@pytest.mark.parametrize('messages', [[], [{'role': 'user', 'content': ' '}],
                                      [{'role': 'tool', 'content': 'Hi'}],
                                      [{'role': 'assistant', 'content': 'Hi'}],
                                      [{'role': 'user', 'content': 'x' * 10001}],
                                      [{'role': 'user', 'content': 'x' * 9000}] * 7])
def test_invalid_messages_are_rejected_before_calling_provider(client, configured, messages):
    assert client.post('/api/llm/chat', json={'messages': messages}).status_code == 422
