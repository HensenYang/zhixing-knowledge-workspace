"""Interactive local database setup. Never prints credentials."""
import getpass
import os
from pathlib import Path
import secrets
from urllib.parse import quote

import psycopg2
from dotenv import dotenv_values
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
env_path = ROOT / '.env'
preserved_env = ''
if env_path.exists():
    current = dotenv_values(env_path)
    if (current.get('DATABASE_URL') or '').strip():
        raise SystemExit('A configured local .env already exists. It was preserved. Use migrate.py to apply migrations.')
    # MCP and other optional local settings may be configured before the
    # database. Preserve them while replacing only database-owned keys.
    kept = []
    for line in env_path.read_text(encoding='utf-8-sig').splitlines():
        stripped = line.strip()
        key = stripped.split('=', 1)[0].strip() if '=' in stripped and not stripped.startswith('#') else ''
        if key not in {'DATABASE_URL', 'STORAGE_ROOT'}:
            kept.append(line)
    preserved_env = '\n'.join(kept).strip()

host = input('PostgreSQL host [127.0.0.1]: ').strip() or '127.0.0.1'
port = input('Port [5432]: ').strip() or '5432'
user = input('Administrator [postgres]: ').strip() or 'postgres'
password = ''
while not password:
    password = getpass.getpass('Administrator password (input is hidden): ')
    if not password:
        print('Password cannot be empty. Type the PostgreSQL administrator password, then press Enter.')
database = 'embodied_knowledge'
role = 'knowledge_app'
try:
    connection = psycopg2.connect(host=host, port=port, user=user, password=password, dbname='postgres', connect_timeout=8)
except psycopg2.OperationalError as error:
    detail = str(error).lower()
    if 'password authentication failed' in detail:
        raise SystemExit('PostgreSQL rejected the administrator password. Re-run setup and enter the password configured for this account.') from None
    if 'connection refused' in detail or 'could not connect to server' in detail:
        raise SystemExit('Cannot reach PostgreSQL. Confirm that the PostgreSQL service is running and that host/port are correct.') from None
    raise SystemExit('Could not authenticate to PostgreSQL. Check the administrator account, password, host, and port.') from None
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
content = f'DATABASE_URL={dsn}\nSTORAGE_ROOT=storage\n'
if preserved_env:
    content += f'\n{preserved_env}\n'
temporary_env = ROOT / '.env.setup.tmp'
temporary_env.write_text(content, encoding='utf-8')
temporary_env.replace(env_path)
os.environ['DATABASE_URL'] = dsn
from migrate import migrate
migrate()
print('Database configured and migrations applied. Credentials remain in the local .env.')

