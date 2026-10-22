"""Shared test helpers. The `client` fixture lives in conftest.py."""
import os
from pathlib import Path
import time
from uuid import uuid4

DSN = os.environ.get('TEST_DATABASE_URL')
MIGRATIONS = sorted((Path(__file__).resolve().parents[2] / 'database/migrations').glob('V*.sql'))


def migrate_schema(cursor, schema):
    """Apply every migration to a scratch schema (the files say `knowledge.`; the name is swapped)."""
    for migration in MIGRATIONS:
        cursor.execute(migration.read_text(encoding='utf-8').replace('knowledge.', f'{schema}.').replace('CREATE SCHEMA knowledge;', f'CREATE SCHEMA {schema};'))


def wait_for_job(client, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f'/api/jobs/{job_id}').json()
        if job['status'] in ('succeeded', 'failed'):
            return job
        time.sleep(0.05)
    raise AssertionError('background job did not finish')


def create(client, title='机器人动作', kind='concept'):
    response = client.post('/api/objects', json={'title': title, 'kind': kind, 'body_md': '中文笔记 $a_t=\\pi(o_t)$', 'tags': ['机器人', 'VLA']})
    assert response.status_code == 201, response.text
    return response.json()


def canvas_item(object_id, x=0, parent_id=None):
    return {'id': str(uuid4()), 'item_type': 'object', 'object_id': object_id, 'parent_id': parent_id, 'x': x, 'y': 0, 'width': 260, 'height': 160, 'properties': {}}
