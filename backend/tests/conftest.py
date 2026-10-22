"""Each test gets its own schema in the isolated test database (TEST_DATABASE_URL) and its own attachment
folder; both are removed afterwards."""
from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg2
from psycopg2 import sql
import pytest

import backend.app as workspace
from helpers import DSN, migrate_schema


@pytest.fixture
def client(monkeypatch, tmp_path):
    if not DSN:
        pytest.skip('Only run against an explicitly configured isolated test database (TEST_DATABASE_URL).')
    schema = 'test_' + uuid4().hex
    with psycopg2.connect(DSN) as connection:
        with connection.cursor() as cursor:
            migrate_schema(cursor, schema)
    monkeypatch.setenv('DATABASE_URL', DSN)
    monkeypatch.setattr(workspace, 'SCHEMA', schema)
    monkeypatch.setattr(workspace, 'STORAGE', tmp_path)
    (tmp_path / 'attachments').mkdir()
    with TestClient(workspace.app) as test_client:
        yield test_client
    with psycopg2.connect(DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


@pytest.fixture
def as_workspace():
    """Starting a background job outside a request. Nothing to set up in the single-user app; the
    multi-user version (several workspaces) sets the signed-in user and workspace here."""
    @contextmanager
    def enter(client):
        yield None
    return enter
