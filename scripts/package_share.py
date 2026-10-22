"""Build a credential-free collaborator package from live database content.

Run from the project root with .venv/Scripts/python.exe scripts/package_share.py.
"""
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.api.backup import export_backup, inspect_backup

DATE = '2026-10-20'
PREFIX = 'Embodied-Knowledge-Workspace/'
OUTPUT = ROOT / 'dist-share'

def active(rows):
    return [row for row in rows if not row.get('deleted_at')]

def seed_backup():
    raw = zipfile.ZipFile(io.BytesIO(export_backup().body))
    manifest = json.loads(raw.read('manifest.json'))
    tables = manifest['tables']
    for table in ['objects', 'relations', 'canvases', 'experiment_runs', 'attachments']:
        tables[table] = active(tables[table])
    ids = lambda table: {row['id'] for row in tables[table]}
    tables['relations'] = [row for row in tables['relations'] if row['source_id'] in ids('objects') and row['target_id'] in ids('objects')]
    tables['relation_evidence'] = [row for row in tables['relation_evidence'] if row['relation_id'] in ids('relations')]
    for row in tables['relation_evidence']:
        if row.get('evidence_object_id') not in ids('objects'):
            row['evidence_object_id'] = None
    tables['object_tags'] = [row for row in tables['object_tags'] if row['object_id'] in ids('objects')]
    tags = {row['tag_id'] for row in tables['object_tags']}
    tables['tags'] = [row for row in tables['tags'] if row['id'] in tags]
    tables['canvas_items'] = [row for row in tables['canvas_items'] if row['canvas_id'] in ids('canvases')]
    for row in tables['canvas_items']:
        if row.get('object_id') and row['object_id'] not in ids('objects'):
            row.update(object_id=None, item_type='text', properties={'text': '原引用条目未包含在共享资料中'})
    tables['canvas_edges'] = [row for row in tables['canvas_edges'] if row['canvas_id'] in ids('canvases') and row['source_item_id'] in ids('canvas_items') and row['target_item_id'] in ids('canvas_items')]
    for row in tables['canvas_edges']:
        if row.get('relation_id') not in ids('relations'):
            row['relation_id'] = None
    tables['experiment_runs'] = [row for row in tables['experiment_runs'] if row['experiment_id'] in ids('objects') and row['status'] == 'planned']
    for table in ['learning_sessions', 'session_objects', 'object_revisions', 'canvas_revisions', 'run_artifacts']:
        tables[table] = []
    tables['object_attachments'] = [row for row in tables['object_attachments'] if row['object_id'] in ids('objects') and row['attachment_id'] in ids('attachments')]
    attachments = {row['attachment_id'] for row in tables['object_attachments']}
    tables['attachments'] = [row for row in tables['attachments'] if row['id'] in attachments]
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
        for row in tables['objects']:
            archive.writestr(f"notes/{row['id']}.md", row['body_md'])
        for row in tables['attachments']:
            archive.writestr(row['relative_path'], raw.read(row['relative_path']))
    raw.close()
    inspected, _ = inspect_backup(output.getvalue())
    assert inspected.testzip() is None
    inspected.close()
    return output.getvalue(), {table: len(rows) for table, rows in tables.items()}

def main():
    seed, counts = seed_backup()
    files = {}
    excluded_parts = {'node_modules', '.venv', '__pycache__', '.pytest_cache', 'dist', 'test-results'}
    roots = ['backend', 'database', 'scripts', 'frontend_Web/src', 'frontend_Web/public', 'frontend_Web/tests', 'research/unitree-group-01/notes', 'research/unitree-group-01/sources']
    for name in roots:
        directory = ROOT / name
        if not directory.exists():
            continue
        for path in directory.rglob('*'):
            if path.is_file() and not (set(path.relative_to(ROOT).parts) & excluded_parts) and path.suffix not in {'.pyc', '.log', '.pid'}:
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ['.env.example', '.gitignore', 'docs/phase-1-design.md', 'docs/share-guide.md']:
        files[name] = (ROOT / name).read_bytes()
    for name in ['index.html', 'package.json', 'package-lock.json', 'vite.config.js', 'postcss.config.js', 'tailwind.config.js', 'playwright.config.js']:
        files['frontend_Web/' + name] = (ROOT / 'frontend_Web' / name).read_bytes()
    for name in ['README.md', 'source-manifest.json', 'snapshot-inventory.json', 'workspace-links.md']:
        files['research/unitree-group-01/' + name] = (ROOT / 'research/unitree-group-01' / name).read_bytes()
    files['README.md'] = (ROOT / 'docs/share-guide.md').read_bytes()
    files['shared-data/knowledge-seed.zip'] = seed
    sources = '# 第三方资料来源（Third-party Sources）\n\n'
    for repository in ['unitreerobotics/unifolm-world-model-action', 'unitreerobotics/unifolm-vla', 'unitreerobotics/unifolm-wla']:
        sources += f'- 官方仓库及许可入口：https://github.com/{repository} （参见 LICENSE、NOTICE、THIRD_PARTY_LICENSES 等原始文件，如有）。\n'
    sources += '\n其他论文与模型卡片的出处见研究笔记；文本快照来自研究时固定的版本，不代表已获独立的再许可。项目依赖的许可见各依赖包本身。\n'
    files['THIRD-PARTY-SOURCES.md'] = sources.encode('utf-8')
    # Compare against actual local credential strings without logging them.
    from dotenv import dotenv_values
    from urllib.parse import urlparse, unquote
    dsn = dotenv_values(ROOT / '.env').get('DATABASE_URL', '')
    secret = urlparse(dsn).password if dsn else None
    prohibited = [value.encode() for value in [dsn, secret, unquote(secret) if secret else None] if value]
    for name, content in files.items():
        assert Path(name).name != '.env' and not any(part in excluded_parts for part in Path(name).parts), name
        assert not any(value in content for value in prohibited), f'Local credential found in {name}'
    assert not any(value in zipfile.ZipFile(io.BytesIO(seed)).read('manifest.json') for value in prohibited)
    manifest = {'package_date': DATE, 'format': 'embodied-knowledge-share', 'seed_counts': counts,
                'personal_logs_and_revisions_included': False, 'runtime_dependencies_included': False,
                'files': {name: {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()} for name, content in sorted(files.items())}}
    files['PACKAGE-MANIFEST.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    OUTPUT.mkdir(exist_ok=True)
    destination = OUTPUT / f'Embodied-Knowledge-Workspace-{DATE}.zip'
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(PREFIX + name, content)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        for name, item in manifest['files'].items():
            assert hashlib.sha256(archive.read(PREFIX + name)).hexdigest() == item['sha256']
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.zip.sha256').write_text(f'{digest}  {destination.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(destination), 'bytes': destination.stat().st_size, 'files': len(files), 'seed_counts': counts, 'sha256': digest}, ensure_ascii=False))

if __name__ == '__main__':
    main()
