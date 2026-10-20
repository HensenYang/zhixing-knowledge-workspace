"""Add study navigation, verify persisted records, and export a recovery copy."""
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path
from import_workspace import api, ROOT

report = json.loads((ROOT / 'workspace-import.json').read_text(encoding='utf-8'))
bundle = json.loads((ROOT / 'bundle.json').read_text(encoding='utf-8'))
objects = {item['key']: item for item in bundle['objects']}
def link(key):
    return f"[{objects[key]['title']}](http://127.0.0.1:5174/knowledge/{report['objects'][key]})"

navigation = '\n\n## 工作台阅读入口（Workspace Reading Links）\n\n' + '\n'.join(
    '- ' + link(key) for key in ['comparison', 'model:wma', 'model:vla', 'model:er1', 'model:flow', 'model:wla', 'actions', 'runbook', 'gaps', 'talk', 'task:01']
) + f"\n- [研究画布（Study Canvas）](http://127.0.0.1:5174/canvases/{report['canvas_id']})\n"
template = '''

## 开始阅读（Start Reading）

先读{comparison}，再打开各模型笔记核对源码与官方资料。

## 你的填写模板（Your Worksheet）

| 模型（Model） | 输入（Input） | 输出（Output） | 用途（Use） | 原始出处（Primary Source） |
|---|---|---|---|---|
| WMA-0 | 待填写 | 待填写 | 待填写 | 待填写 |
| VLA-0 | 待填写 | 待填写 | 待填写 | 待填写 |
| ER-1 | 待填写 | 待填写 | 待填写 | 待填写 |
| ER-Flow | 待填写 | 待填写 | 待填写 | 待填写 |
| WLA-1.0 | 待填写 | 待填写 | 待填写 | 待填写 |

自检：ER-1的推理输出怎样才能用于机器人控制？ER-Flow的光流（Optical Flow）与动作专家的流匹配（Flow Matching）分别处理什么？WMA预测的未来视频与ER-Flow的动态区域掩码有什么区别？

完成后在学习轨迹中记录你自己的解释、仍不确定的地方，并关联本任务。助手整理资料不计作你已完成学习。
'''.format(comparison=link('comparison'))
for key, suffix, marker in [('hub', navigation, '## 工作台阅读入口'), ('task:01', template, '## 你的填写模板')]:
    stored = api('/objects/' + report['objects'][key])
    if marker not in stored['body_md']:
        fields = ['kind', 'title', 'summary', 'body_md', 'source_url', 'reading_status', 'mastery_status', 'metadata', 'tags', 'version', 'archived_at']
        payload = {field: stored[field] for field in fields}
        payload['body_md'] += suffix
        api('/objects/' + stored['id'], payload, 'PATCH')
    local = ROOT / 'notes' / (key.replace(':', '-') + '.md')
    content = local.read_text(encoding='utf-8')
    if marker not in content:
        local.write_text(content + suffix, encoding='utf-8')

links = '# 第一组工作台入口（Workspace Links）\n\n' + navigation
(ROOT / 'workspace-links.md').write_text(links, encoding='utf-8')

manifest = json.loads((ROOT / 'source-manifest.json').read_text(encoding='utf-8'))
for source in manifest:
    path = ROOT / source['local_path']
    if not path.is_file():
        continue  # Source snapshots are optional local caches, absent in a fresh clone.
    source['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    source['verified_on'] = '2026-10-01'
(ROOT / 'source-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
inventory = [{'local_path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted((ROOT / 'sources').rglob('*')) if path.is_file()]
if inventory:
    (ROOT / 'snapshot-inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')

graph = api('/graph')
assert set(report['objects'].values()).issubset({node['id'] for node in graph['nodes']})
assert set(report['relations'].values()).issubset({edge['id'] for edge in graph['edges']})
canvas = api('/canvases/' + report['canvas_id'])
if canvas['viewport'] == {'x': 30, 'y': 120, 'zoom': 0.38}:
    payload = {field: canvas[field] for field in ['title', 'version', 'items', 'edges']}
    payload['viewport'] = {'x': 18, 'y': 105, 'zoom': 0.30}
    api('/canvases/' + report['canvas_id'] + '/document', payload, 'PUT')
    canvas = api('/canvases/' + report['canvas_id'])
assert len(canvas['items']) == 26 and len(canvas['edges']) == 20
item_ids = {item['id'] for item in canvas['items']}
assert all(edge['source_item_id'] in item_ids and edge['target_item_id'] in item_ids for edge in canvas['edges'])
runs = {run['id']: run for run in api('/runs')}
assert all(runs[identifier]['status'] == 'planned' and not runs[identifier]['metrics'] for identifier in report['planned_runs'])
backup = ROOT.parents[1] / 'storage' / 'exports' / 'unitree-group-01-backup.zip'
data = urllib.request.urlopen('http://127.0.0.1:8001/api/export', timeout=45).read()
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    assert archive.testzip() is None
backup.write_bytes(data)
print(json.dumps({'objects': len(report['objects']), 'relations': len(report['relations']), 'canvas_items': len(canvas['items']), 'canvas_edges': len(canvas['edges']), 'planned_runs': len(report['planned_runs']), 'backup_bytes': len(data)}, ensure_ascii=False))
