"""Interactive local database setup. Never prints credentials."""
import getpass
import os
from pathlib import Path
import secrets
from urllib.parse import quote

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
host = input('PostgreSQL host [127.0.0.1]: ').strip() or '127.0.0.1'
port = input('Port [5432]: ').strip() or '5432'
user = input('Administrator [postgres]: ').strip() or 'postgres'
password = getpass.getpass('Administrator password (local input only): ')
database = 'embodied_knowledge'
role = 'knowledge_app'
env_path = ROOT / '.env'
if env_path.exists():
    raise SystemExit('A local .env already exists. It was preserved. Use migrate.py to apply migrations.')
connection = psycopg2.connect(host=host, port=port, user=user, password=password, dbname='postgres', connect_timeout=8)
connection.autocommit = True
app_password = secrets.token_urlsafe(32)
with connection.cursor() as cursor:
    cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
    if cursor.fetchone():
        raise SystemExit('knowledge_app already exists. Existing role was preserved; configure .env manually.')
    cursor.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,))
    if cursor.fetchone():
        raise SystemExit('embodied_knowledge already exists. Existing database was preserved; configure .env manually.')
    cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(role), sql.Literal(app_password)))
    cursor.execute(sql.SQL('CREATE DATABASE {} OWNER {} ENCODING {} TEMPLATE template0').format(sql.Identifier(database), sql.Identifier(role), sql.Literal('UTF8')))
connection.close()
dsn = f'postgresql://{quote(role, safe="")}:{quote(app_password, safe="")}@{host}:{port}/{database}'
env_path.write_text(f'DATABASE_URL={dsn}\nSTORAGE_ROOT=storage\n', encoding='utf-8')
os.environ['DATABASE_URL'] = dsn
from migrate import migrate
migrate()
print('Database configured and migrations applied. Credentials remain in the local .env.')

