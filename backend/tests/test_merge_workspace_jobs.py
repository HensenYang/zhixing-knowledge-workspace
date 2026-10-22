"""Merge regression: pooled requests and worker threads keep workspace boundaries."""
from backend import jobs
from backend import pool
from helpers import wait_for_job
import pytest


def test_job_progress_and_results_are_private_to_the_request_workspace(client, as_workspace):
    with as_workspace(client):
        owner_job = jobs.submit('test', lambda report: {'private': 'owner result'})
    assert wait_for_job(client, owner_job)['result'] == {'private': 'owner result'}
    other = client.post('/api/auth/register', json={
        'email': 'other@example.test', 'display_name': 'Other owner', 'password': 'test-password-123'})
    assert other.status_code == 201
    assert client.get('/api/jobs').json() == []
    assert client.get('/api/jobs/' + owner_job).status_code == 404
    with as_workspace(client):
        other_job = jobs.submit('test', lambda report: {'private': 'other result'})
    assert wait_for_job(client, other_job)['result'] == {'private': 'other result'}
    assert client.post('/api/auth/login', json={
        'email': 'owner@example.test', 'password': 'test-password-123'}).status_code == 200
    assert client.get('/api/jobs/' + other_job).status_code == 404
    assert [job['id'] for job in client.get('/api/jobs').json()] == [owner_job]


def test_pool_releases_the_slot_when_transaction_preparation_fails():
    connection = object()
    released = []

    class FakePool:
        def acquire(self):
            return connection

        def release(self, item, discard=False):
            released.append((item, discard))

    def fail(_connection):
        raise ValueError('invalid transaction setup')

    with pytest.raises(ValueError, match='invalid transaction setup'):
        pool.checkout(FakePool(), fail)
    assert released == [(connection, True)]
