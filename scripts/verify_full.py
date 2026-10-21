"""Disposable PostgreSQL, real API and browser regression run."""
import os, socket, subprocess, sys, time, json
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
import argparse
parser=argparse.ArgumentParser(description='Run a full regression against a fresh, disposable PostgreSQL cluster. Never reads the personal .env.')
parser.add_argument('--postgres-bin',type=Path,default=Path(__file__).resolve().parents[1]/'storage/runtime/pgsql/bin')
parser.add_argument('--node',type=Path,default=Path(__file__).resolve().parents[1]/'storage/runtime/node-v22.23.3-win-x64/node.exe')
parser.add_argument('--browser-fallback',action='store_true',help='Use the single-process Playwright fallback if CLI workers cannot start.')
parser.add_argument('--spec',action='append',default=[],help='Limit browser specs (may be repeated).')
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'storage/full-tests'/datetime.now().strftime('%Y%m%d-%H%M%S')
RUN.mkdir(parents=True)
BIN=args.postgres_bin.resolve()
NODE=args.node.resolve()
if not NODE.is_file() or not (BIN/'initdb.exe').is_file(): raise SystemExit('Provide installed Node and PostgreSQL binaries with --node and --postgres-bin.')
NPM=NODE.parent/'node_modules/npm/bin/npm-cli.js'
if not NPM.is_file(): NPM=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'nodejs/node_modules/npm/bin/npm-cli.js'
PYTHON=Path(sys.executable)
ENV=dict(os.environ)
EMPTY=RUN/'empty.env'
EMPTY.write_text('',encoding='utf8')
ENV.update(WORKSPACE_ENV_FILE=str(EMPTY), STORAGE_ROOT=str(RUN/'files'), LLM_API_KEY='', LLM_MODEL='', KNOWLEDGE_SCHEMA='knowledge', PYTHONUNBUFFERED='1')
ENV['PATH']=str(NODE.parent)+os.pathsep+ENV.get('PATH','')
for name in ('TEST_DATABASE_URL','DATABASE_URL'): ENV.pop(name,None)
def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]
def run(args, name, cwd=ROOT, timeout=600):
    print('START '+name,flush=True)
    with (RUN/(name+'.log')).open('w',encoding='utf8') as log:
        try: code=subprocess.run(list(map(str,args)),cwd=cwd,env=ENV,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired: code=124
    print('END '+name+' code='+str(code),flush=True)
    results[name]=code
    return code
def ready(url, process):
    for _ in range(120):
        if process.poll() is not None: raise RuntimeError('Server exited: '+url)
        try:
            with urlopen(url,timeout=1) as response:
                if response.status==200: return
        except Exception: time.sleep(.25)
    raise RuntimeError('Server readiness timed out: '+url)
results={}; servers=[]; logs=[]; started=False
try:
    run([BIN/'initdb.exe','-D',RUN/'pgdata','-U','test_admin','-A','trust','--encoding=UTF8','--locale=C'],'initdb',timeout=60)
    if results['initdb']: raise RuntimeError('initdb failed')
    db_port,api_port,web_port=port(),port(),port()
    if run([BIN/'pg_ctl.exe','-D',RUN/'pgdata','-l',RUN/'postgres.log','-o',f'-h 127.0.0.1 -p {db_port}','-w','start'],'postgres-start',timeout=60): raise RuntimeError('Postgres failed')
    started=True
    # Use a non-superuser: otherwise PostgreSQL bypasses FORCE ROW LEVEL SECURITY.
    import psycopg2
    connection=psycopg2.connect(host='127.0.0.1',port=db_port,user='test_admin',dbname='postgres')
    connection.autocommit=True
    with connection.cursor() as cursor:
        cursor.execute('CREATE ROLE test_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
        cursor.execute('CREATE DATABASE workspace_test OWNER test_user')
    connection.close()
    ENV.update(DATABASE_URL=f'postgresql://test_user@127.0.0.1:{db_port}/workspace_test',TEST_DATABASE_URL=f'postgresql://test_user@127.0.0.1:{db_port}/workspace_test')
    frontend=ROOT/'frontend_Web'
    for script in ('check:i18n','test:i18n','test:artifacts','build'):
        run([NODE,NPM,'run',script],script.replace(':','-'),frontend)
    run([NODE,'--test',*sorted(frontend.glob('unit-tests/*.test.mjs'))],'frontend-units',frontend)
    run([PYTHON,'-m','pytest','backend/tests','-q','--junitxml='+str(RUN/'backend.xml')],'backend',timeout=600)
    if run([PYTHON,'scripts/migrate.py'],'migration'): raise RuntimeError('Migration failed')
    ENV.update(WORKSPACE_API_TARGET=f'http://127.0.0.1:{api_port}',WORKSPACE_TEST_URL=f'http://127.0.0.1:{web_port}',PLAYWRIGHT_JSON_OUTPUT_FILE=str(RUN/'browser.json'), WORKSPACE_DISPOSABLE_TEST='1', WORKSPACE_TEST_REPORT_DIR=str(RUN))
    (RUN/'ports.json').write_text(json.dumps({'api':api_port,'web':web_port}),encoding='utf8')
    for name,server_args,cwd in [('api',[PYTHON,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(api_port)],ROOT),('web',[NODE,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(web_port),'--strictPort'],ROOT/'frontend_Web')]:
        log=(RUN/(name+'.log')).open('w',encoding='utf8'); logs.append(log)
        servers.append(subprocess.Popen(list(map(str,server_args)),cwd=cwd,env=ENV,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW))
    ready(f'http://127.0.0.1:{api_port}/api/health',servers[0]); ready(f'http://127.0.0.1:{web_port}',servers[1])
    run([NODE,ROOT/'scripts/run_browser_checks.cjs',*args.spec] if args.browser_fallback else [NODE,'node_modules/@playwright/test/cli.js','test',*args.spec,'--reporter=list,json'],'browser',ROOT/'frontend_Web',timeout=1200)
finally:
    for process in reversed(servers):
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill()
    for log in logs: log.close()
    if started: run([BIN/'pg_ctl.exe','-D',RUN/'pgdata','-m','fast','-w','stop'],'postgres-stop',timeout=60)
    (RUN/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    print('REPORT '+str(RUN),flush=True)
sys.exit(int(any(results.values())))
