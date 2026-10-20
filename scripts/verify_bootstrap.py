"""Validate interactive bootstrap against the isolated local test cluster."""
import builtins
import getpass
import os
from pathlib import Path
import runpy
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'storage/bootstrap-test'
if (target/'.env').exists():
    raise SystemExit('Bootstrap fixture already exists; preserve it and use a fresh test cluster for another run.')
(target/'scripts').mkdir(parents=True,exist_ok=True)
(target/'database/migrations').mkdir(parents=True,exist_ok=True)
for name in ['setup_database.py','migrate.py']:
    shutil.copy2(ROOT/'scripts'/name,target/'scripts'/name)
shutil.copy2(ROOT/'database/migrations/V001__knowledge_workspace.sql',target/'database/migrations/V001__knowledge_workspace.sql')
answers=iter(['127.0.0.1','55432','knowledge_test'])
builtins.input=lambda prompt:next(answers)
getpass.getpass=lambda prompt:''
sys.path.insert(0,str(target/'scripts'))
runpy.run_path(str(target/'scripts/setup_database.py'),run_name='__main__')
import psycopg2
with psycopg2.connect(os.environ['DATABASE_URL']) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_user, current_database()')
        row=cursor.fetchone()
        assert row==('knowledge_app','embodied_knowledge'),row
        cursor.execute('SELECT version FROM knowledge.schema_migrations')
        assert cursor.fetchone()[0]=='V001'
print('Independent role, database, local credential file and application login verified on test port 55432.')

