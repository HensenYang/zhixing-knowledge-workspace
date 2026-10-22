"""Oracle container entry point. The ordinary development server is unchanged."""
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen


def application_dsn():
    password = os.environ['POSTGRES_APP_PASSWORD']
    if not password:
        raise ValueError('POSTGRES_APP_PASSWORD is required')
    return 'postgresql://knowledge_app:' + quote(password, safe='') + '@db:5432/zhixing'


class ProxyGate:
    def __init__(self, app, secret):
        if not secret or len(secret) < 32:
            raise ValueError('DEPLOYMENT_PROXY_SECRET must contain at least 32 characters')
        self.app, self.secret = app, secret.encode('utf-8')

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            supplied = dict(scope.get('headers', [])).get(b'x-zhixing-proxy-secret', b'')
            if not hmac.compare_digest(supplied, self.secret):
                from starlette.responses import JSONResponse
                await JSONResponse({'detail': 'deployment.originDenied'}, status_code=404,
                                   headers={'Cache-Control': 'no-store'})(scope, receive, send)
                return
        await self.app(scope, receive, send)


def bootstrap():
    import psycopg2
    from psycopg2 import sql
    connection = psycopg2.connect(host='db', dbname='postgres', user='postgres',
                                  password=os.environ['POSTGRES_ADMIN_PASSWORD'], connect_timeout=10)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='knowledge_app'")
            if not cursor.fetchone():
                cursor.execute('CREATE ROLE knowledge_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS')
            cursor.execute(sql.SQL('ALTER ROLE knowledge_app WITH PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS')
                           .format(sql.Literal(os.environ['POSTGRES_APP_PASSWORD'])))
            cursor.execute("SELECT 1 FROM pg_database WHERE datname='zhixing'")
            if not cursor.fetchone():
                cursor.execute('CREATE DATABASE zhixing OWNER knowledge_app')
    finally:
        connection.close()
    environment = {**os.environ, 'DATABASE_URL': application_dsn(), 'WORKSPACE_ENV_FILE': '/dev/null'}
    subprocess.run([sys.executable, str(Path(__file__).resolve().parents[2] / 'scripts/migrate.py')],
                   env=environment, check=True)


def serve():
    os.environ['DATABASE_URL'] = application_dsn()
    os.environ['WORKSPACE_ENV_FILE'] = '/dev/null'
    from backend.app import app
    import uvicorn
    app.add_middleware(ProxyGate, secret=os.environ['DEPLOYMENT_PROXY_SECRET'])
    # One process: in-process jobs cannot be shared between multiple workers.
    uvicorn.run(app, host='0.0.0.0', port=8001, workers=1, proxy_headers=False)


def health():
    request = Request('http://127.0.0.1:8001/api/health',
                      headers={'X-Zhixing-Proxy-Secret': os.environ['DEPLOYMENT_PROXY_SECRET']})
    with urlopen(request, timeout=8) as response:
        if json.load(response).get('database') != 'ready':
            raise SystemExit(1)


if __name__ == '__main__':
    {'bootstrap': bootstrap, 'serve': serve, 'health': health}[sys.argv[1]]()
