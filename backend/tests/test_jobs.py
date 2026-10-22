"""Background jobs: progress, failure handling, restart recovery and the asynchronous restore."""
import threading
import time
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import psycopg2
import pytest

import backend.app as workspace
from backend import jobs
from helpers import DSN, create, migrate_schema, wait_for_job

pytestmark = pytest.mark.skipif(not DSN, reason='Only run against an explicitly configured isolated test database.')


def wait_until(check, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError('condition not reached')


def test_progress_is_visible_while_a_job_is_still_running(client, as_workspace):
    release = threading.Event()

    def work(report):
        report(40, '写到一半')
        assert release.wait(10)
        return {'done': True}

    with as_workspace(client):
        job_id = jobs.submit('test', work)
    running = wait_until(lambda: (lambda job: job if job['progress'] == 40 else None)(client.get(f'/api/jobs/{job_id}').json()))
    assert running['status'] == 'running' and running['message'] == '写到一半' and running['started_at'] and not running['finished_at']
    release.set()
    done = wait_for_job(client, job_id)
    assert done['status'] == 'succeeded' and done['progress'] == 100 and done['result'] == {'done': True} and done['finished_at']
    assert [item['id'] for item in client.get('/api/jobs?kind=test').json()] == [job_id]
    assert client.get('/api/jobs?kind=other').json() == []
    assert client.get(f'/api/jobs/{uuid4()}').status_code == 404


def test_failed_jobs_report_why_and_the_worker_keeps_going(client, as_workspace):
    def explode(report):
        raise RuntimeError('internal detail that should not reach the user')

    def refuse(report):
        raise HTTPException(409, '这是给用户看的原因')

    with as_workspace(client):
        first, second = jobs.submit('test', explode), jobs.submit('test', refuse)
        after = jobs.submit('test', lambda report: {'ok': 1})
    internal, expected, fine = (wait_for_job(client, job_id) for job_id in (first, second, after))
    assert internal['status'] == 'failed' and 'internal detail' not in internal['error'] and '服务日志' in internal['error']
    assert expected['status'] == 'failed' and expected['error'] == '这是给用户看的原因'
    assert fine['status'] == 'succeeded'


def test_jobs_left_running_by_a_previous_process_are_marked_failed_on_start(client):
    workspace_id = client.get('/api/auth/me').json()['workspaces'][0]['id']
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.workspace_id',%s,true)", (workspace_id,))
        cursor.execute(f"INSERT INTO {workspace.SCHEMA}.background_jobs(kind,status,progress) VALUES ('import','running',50),('import','queued',0),('import','succeeded',100) RETURNING id")
        running, queued, finished = [row[0] for row in cursor.fetchall()]
    with TestClient(workspace.app) as restarted:
        restarted.cookies.update(client.cookies)
        assert [restarted.get(f'/api/jobs/{job_id}').json()['status'] for job_id in (running, queued, finished)] == ['failed', 'failed', 'succeeded']
        assert '重启' in restarted.get(f'/api/jobs/{running}').json()['error']


def export_zip(client):
    response = client.get('/api/export')
    assert response.status_code == 200
    return response.content


def test_restore_failure_removes_attachment_files_it_already_wrote(client, monkeypatch, tmp_path):
    note = create(client, '带附件的笔记')
    for name in ('first.txt', 'second.txt'):
        assert client.post(f"/api/objects/{note['id']}/attachments", files={'file': (name, name.encode(), 'text/plain')}).status_code == 201
    attachments = {row['original_name']: row for row in client.get(f"/api/objects/{note['id']}/attachments").json()}
    backup = export_zip(client)
    target = 'test_' + uuid4().hex
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        migrate_schema(cursor, target)
    destination = tmp_path / 'restored'
    (destination / 'attachments').mkdir(parents=True)
    # The second attachment's file already exists at the destination, so writing it fails after the first one was written.
    blocker = destination / attachments['second.txt']['relative_path']
    blocker.write_bytes(b'already here')
    original_schema, original_storage = workspace.SCHEMA, workspace.STORAGE
    monkeypatch.setattr(workspace, 'SCHEMA', target)
    monkeypatch.setattr(workspace, 'STORAGE', destination)
    try:
        registered = client.post('/api/auth/register', json={'email':'restore@example.test','display_name':'Restore owner','password':'test-password-123'})
        assert registered.status_code == 201, registered.text
        started = client.post('/api/import?dry_run=false', files={'file': ('b.zip', backup, 'application/zip')})
        assert started.status_code == 202, started.text
        job = wait_for_job(client, started.json()['job_id'])
        written = [path for path in (destination / 'attachments').iterdir() if path != blocker]
        assert job['status'] == 'failed' and '附件路径冲突' in job['error']
        assert written == [] and blocker.read_bytes() == b'already here'
        assert client.get('/api/objects').json() == []
    finally:
        monkeypatch.setattr(workspace, 'SCHEMA', original_schema)
        monkeypatch.setattr(workspace, 'STORAGE', original_storage)
        with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA {target} CASCADE')


def test_conflicts_are_refused_before_any_job_starts(client):
    create(client, '已存在的笔记')
    backup = export_zip(client)
    refused = client.post('/api/import?dry_run=false', files={'file': ('b.zip', backup, 'application/zip')})
    assert refused.status_code == 409 and client.get('/api/jobs').json() == []
    preview = client.post('/api/import?dry_run=true', files={'file': ('b.zip', backup, 'application/zip')})
    assert preview.status_code == 200 and preview.json()['conflicts']['objects'] == 1 and 'job_id' not in preview.json()


def test_a_slow_link_check_does_not_hold_up_a_restore(client, as_workspace):
    release = threading.Event()

    def slow(report):
        report(10, '等待外部网站')
        assert release.wait(10)
        return {}

    with as_workspace(client):
        slow_id = jobs.submit('link_check', slow)
        wait_until(lambda: client.get(f'/api/jobs/{slow_id}').json()['status'] == 'running')
        quick_id = jobs.submit('import', lambda report: {'restored': True})
    try:
        assert wait_for_job(client, quick_id, timeout=5)['status'] == 'succeeded'
        assert client.get(f'/api/jobs/{slow_id}').json()['status'] == 'running'
    finally:
        release.set()
    assert wait_for_job(client, slow_id)['status'] == 'succeeded'
