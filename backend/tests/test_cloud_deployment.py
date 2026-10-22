from urllib.parse import unquote, urlsplit

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
import pytest

from deploy.oracle.prepare import prepare
from deploy.oracle.runtime import ProxyGate, application_dsn


def test_server_configuration_generates_unique_secrets_and_never_overwrites(tmp_path):
    destination=prepare(tmp_path)
    original=destination.read_text(encoding='utf-8')
    values=dict(line.split('=',1) for line in original.splitlines() if '=' in line and not line.startswith('#'))
    secrets=[values[key] for key in ('POSTGRES_ADMIN_PASSWORD','POSTGRES_APP_PASSWORD','API_PROXY_SECRET')]
    assert len(set(secrets))==3 and all(len(secret)>=32 for secret in secrets)
    assert values['CLOUDFLARE_TUNNEL_TOKEN']==values['LLM_API_KEY']==''
    with pytest.raises(FileExistsError):
        prepare(tmp_path)
    assert destination.read_text(encoding='utf-8')==original


def test_application_database_uses_an_ordinary_role_and_encodes_password(monkeypatch):
    monkeypatch.setenv('POSTGRES_APP_PASSWORD',"password /:@?#%'科学")
    parsed=urlsplit(application_dsn())
    assert parsed.username=='knowledge_app' and parsed.hostname=='db' and parsed.path=='/zhixing'
    assert unquote(parsed.password)=="password /:@?#%'科学"


def test_origin_gate_rejects_direct_requests_before_reaching_handlers_and_keeps_cookies():
    secret='server-only-secret-'*3
    app=FastAPI()
    calls=[]

    @app.get('/api/health')
    def health(response: Response):
        calls.append('called')
        response.set_cookie('knowledge_session','test-value',secure=True,httponly=True,samesite='lax')
        return {'database':'ready'}

    app.add_middleware(ProxyGate,secret=secret)
    with TestClient(app,base_url='https://app.example.test') as client:
        assert client.get('/api/health').status_code==404
        assert client.get('/api/health',headers={'X-Zhixing-Proxy-Secret':'wrong'}).status_code==404
        assert calls==[]
        response=client.get('/api/health',headers={'X-Zhixing-Proxy-Secret':secret})
        assert response.json()=={'database':'ready'}
        assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
        assert calls==['called']


def test_origin_gate_refuses_an_empty_deployment_secret():
    with pytest.raises(ValueError):
        ProxyGate(None,'')
