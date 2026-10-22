"""Run the Playwright end-to-end tests against a throw-away copy of the database schema.

    TEST_DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/test_db python scripts/run_e2e.py [playwright args]

Creates a scratch schema in the TEST database, starts the backend (port 8002) and the front end
(port 5175) against it, runs the tests, then stops everything and drops the schema. Your real
database is never touched. Needs `npm ci` in frontend_Web first.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PORT, FRONTEND_PORT = 8002, 5175


def wait_for(url, seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise SystemExit(f'Timed out waiting for {url}')


def main():
    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        raise SystemExit('Set TEST_DATABASE_URL to an isolated test database (never your real one).')
    schema = 'e2e_' + uuid.uuid4().hex[:12]
    with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
        for path in sorted((ROOT / 'database/migrations').glob('V*.sql')):
            cursor.execute(path.read_text(encoding='utf-8').replace('knowledge.', f'{schema}.').replace('CREATE SCHEMA knowledge;', f'CREATE SCHEMA {schema};'))
    storage = tempfile.mkdtemp(prefix='e2e-storage-')
    environment = {**os.environ, 'DATABASE_URL': dsn, 'KNOWLEDGE_SCHEMA': schema, 'STORAGE_ROOT': storage, 'WORKSPACE_ENV_FILE': os.devnull,
                   'WORKSPACE_API_TARGET': f'http://127.0.0.1:{BACKEND_PORT}', 'WORKSPACE_DISPOSABLE_TEST': '1'}
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', str(BACKEND_PORT), '--log-level', 'warning'],
                                          cwd=ROOT, env=environment, **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {})))
        node = shutil.which('node') or 'node'
        processes.append(subprocess.Popen([node, 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(FRONTEND_PORT), '--strictPort'],
                                          cwd=ROOT / 'frontend_Web', env=environment, **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {})))
        wait_for(f'http://127.0.0.1:{BACKEND_PORT}/api/health')
        wait_for(f'http://127.0.0.1:{FRONTEND_PORT}/')
        npx = shutil.which('npx') or 'npx'
        result = subprocess.run([npx, 'playwright', 'test', *sys.argv[1:]], cwd=ROOT / 'frontend_Web',
                                env={**environment, 'WORKSPACE_TEST_URL': f'http://127.0.0.1:{FRONTEND_PORT}'})
        return result.returncode
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        shutil.rmtree(storage, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
