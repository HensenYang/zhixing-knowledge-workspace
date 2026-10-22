"""Background jobs: worker threads run jobs and record progress in the database.

Backup restores run one at a time. Link checks, which can take minutes waiting on other people's servers,
have a lane of their own, so they never hold up a restore (for any workspace).

A job's work is a function taking `report(progress, message)`. It runs in a copy of the context of
the request that started it (user and workspace), so row-level security applies to it exactly as it
did to the request; it has its own connection, so the progress it reports is visible to other
requests while its transaction is still open. Jobs that were queued or running when the process
stopped are marked as failed on the next start.
"""
from concurrent.futures import ThreadPoolExecutor
import contextvars
import logging
import threading
from uuid import UUID

from fastapi import APIRouter, HTTPException

import backend.app as workspace

log = logging.getLogger(__name__)
router = APIRouter(prefix='/api/jobs')
SLOW_KINDS = {'link_check'}
_executors = {}
_executor_lock = threading.Lock()


def executor(kind):
    """One worker per lane, created on first use and released by shutdown(), so the app can start again in one process."""
    lane = 'slow' if kind in SLOW_KINDS else 'main'
    with _executor_lock:
        if lane not in _executors:
            _executors[lane] = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f'workspace-job-{lane}')
        return _executors[lane]


def submit(kind, work):
    with workspace.db() as cursor:
        cursor.execute('INSERT INTO background_jobs(kind) VALUES (%s) RETURNING id', (kind,))
        job_id = str(cursor.fetchone()['id'])
    executor(kind).submit(contextvars.copy_context().run, _run, job_id, work)
    return job_id


def _update(sql, parameters):
    with workspace.db() as cursor:
        cursor.execute(sql, parameters)


def _run(job_id, work):
    try:
        _update("UPDATE background_jobs SET status='running', started_at=now() WHERE id=%s", (job_id,))

        def report(progress, message=''):
            _update('UPDATE background_jobs SET progress=%s, message=%s WHERE id=%s', (max(0, min(int(progress), 99)), message, job_id))

        result = work(report)
        _update("UPDATE background_jobs SET status='succeeded', progress=100, message='', result=%s, finished_at=now() WHERE id=%s",
                (workspace.json_value(result), job_id))
    except HTTPException as error:
        _fail(job_id, str(error.detail))
    except Exception:
        log.exception('background job %s failed', job_id)
        _fail(job_id, '任务执行失败，详情见服务日志。')


def _fail(job_id, message):
    try:
        _update("UPDATE background_jobs SET status='failed', error=%s, finished_at=now() WHERE id=%s", (message, job_id))
    except Exception:
        log.exception('could not record the failure of job %s', job_id)


def mark_interrupted():
    """At start-up: whatever was still running belonged to a process that no longer exists. There is
    no request (and so no workspace) here, hence the explicit system marker the table policy allows."""
    try:
        with workspace.db() as cursor:
            cursor.execute("SELECT set_config('app.system','jobs',true)")
            cursor.execute("UPDATE background_jobs SET status='failed', error='服务重启，任务被中断。', finished_at=now() WHERE status IN ('queued','running')")
    except Exception:
        log.warning('could not mark interrupted jobs (database not ready?)')


def shutdown():
    with _executor_lock:
        for pool in _executors.values():
            pool.shutdown(wait=False, cancel_futures=True)
        _executors.clear()


@router.get('')
def recent_jobs(kind: str = '', limit: int = 20):
    with workspace.db() as cursor:
        cursor.execute("SELECT * FROM background_jobs WHERE (%s='' OR kind=%s) ORDER BY created_at DESC LIMIT %s", (kind, kind, min(max(limit, 1), 100)))
        return cursor.fetchall()


@router.get('/{identifier}')
def get_job(identifier: UUID):
    with workspace.db() as cursor:
        return workspace.require(cursor, 'background_jobs', identifier)
