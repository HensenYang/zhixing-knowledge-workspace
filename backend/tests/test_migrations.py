"""Migration hygiene: teammates adding migrations in parallel must not collide."""
from collections import Counter
from pathlib import Path
import re
import uuid

import psycopg2
import pytest

from helpers import DSN, migrate_schema

MIGRATIONS = sorted((Path(__file__).resolve().parents[2] / 'database/migrations').glob('V*.sql'))


def test_versions_are_unique_well_named_and_self_registering():
    versions = [path.name.split('__')[0] for path in MIGRATIONS]
    duplicates = [version for version, count in Counter(versions).items() if count > 1]
    assert not duplicates, f'two migrations share a version: {duplicates}; renumber one of them'
    for path in MIGRATIONS:
        assert re.fullmatch(r'V\d{3}__[a-z0-9_]+\.sql', path.name), f'{path.name}: use V###__lower_snake_name.sql'
        version = path.name.split('__')[0]
        assert f"VALUES ('{version}')" in path.read_text(encoding='utf-8'), f'{path.name} must record its own version in schema_migrations'


@pytest.mark.skipif(not DSN, reason='Only run against an explicitly configured isolated test database.')
def test_all_migrations_apply_to_an_empty_schema_in_order():
    schema = 'migtest_' + re.sub(r'\W', '', uuid.uuid4().hex)
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        try:
            migrate_schema(cursor, schema)
            cursor.execute(f'SELECT version FROM {schema}.schema_migrations ORDER BY version')
            assert [row[0] for row in cursor.fetchall()] == [path.name.split('__')[0] for path in MIGRATIONS]
        finally:
            cursor.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
