import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

def migrate():
    load_dotenv(Path(os.environ.get('WORKSPACE_ENV_FILE', str(ROOT / '.env'))))
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise SystemExit('DATABASE_URL missing. Run scripts/setup_database.ps1 locally.')
    with psycopg2.connect(dsn, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('knowledge.schema_migrations')")
            existing = cursor.fetchone()[0]
            applied = set()
            if existing:
                cursor.execute('SELECT version FROM knowledge.schema_migrations')
                applied = {row[0] for row in cursor.fetchall()}
            for path in sorted((ROOT / 'database/migrations').glob('V*.sql')):
                version = path.name.split('__', 1)[0]
                if version not in applied:
                    cursor.execute(path.read_text(encoding='utf-8'))
                    print(f'Applied {version}')

if __name__ == '__main__':
    migrate()
