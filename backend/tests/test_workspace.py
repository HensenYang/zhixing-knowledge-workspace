import io
import json
import os
from pathlib import Path
from uuid import uuid4
import zipfile

import psycopg2
from psycopg2 import sql
import pytest
from fastapi.testclient import TestClient
import backend.app as workspace

DSN = os.environ.get('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DSN, reason='Only run against an explicitly configured isolated test database.')
MIGRATIONS = sorted((Path(__file__).resolve().parents[2] / 'database/migrations').glob('V*.sql'))
def migrate_schema(cursor,schema):
    for migration in MIGRATIONS:
        cursor.execute(migration.read_text(encoding='utf-8').replace('knowledge.',f'{schema}.').replace('CREATE SCHEMA knowledge;',f'CREATE SCHEMA {schema};'))

@pytest.fixture
def client(monkeypatch,tmp_path):
    schema = 'test_' + uuid4().hex
    with psycopg2.connect(DSN) as connection:
        with connection.cursor() as cursor:
            migrate_schema(cursor,schema)
    monkeypatch.setenv('DATABASE_URL',DSN)
    monkeypatch.setattr(workspace,'SCHEMA',schema)
    monkeypatch.setattr(workspace,'STORAGE',tmp_path)
    (tmp_path/'attachments').mkdir()
    with TestClient(workspace.app) as test_client:
        response=test_client.post('/api/auth/register',json={
            'email':'owner@example.test','display_name':'测试用户','password':'test-password-123'
        })
        assert response.status_code==201,response.text
        yield test_client
    with psycopg2.connect(DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

def create(client,title='机器人动作',kind='concept'):
    response=client.post('/api/objects',json={'title':title,'kind':kind,'body_md':'中文笔记 $a_t=\\pi(o_t)$','tags':['机器人','VLA']})
    assert response.status_code==201,response.text
    return response.json()

def canvas_item(object_id,x=0,parent_id=None):
    return {'id':str(uuid4()),'item_type':'object','object_id':object_id,'parent_id':parent_id,'x':x,'y':0,'width':260,'height':160,'properties':{}}

def test_collaboration_auth_members_comments_reviews_and_isolation(client):
    me=client.get('/api/auth/me')
    assert me.status_code==200 and me.json()['email']=='owner@example.test'
    workspace_id=me.json()['workspaces'][0]['id']
    item=create(client,'需要协作审核')
    comment=client.post('/api/comments',json={'target_type':'object','target_id':item['id'],'body':'请补充证据。'})
    assert comment.status_code==201,comment.text
    assert client.get(f"/api/comments?target_type=object&target_id={item['id']}").json()[0]['display_name']=='测试用户'
    review=client.post('/api/reviews',json={'target_type':'object','target_id':item['id'],'target_version':1,'note':'请审核'})
    assert review.status_code==201,review.text
    decided=client.patch(f"/api/reviews/{review.json()['id']}",json={'status':'approved','note':'通过'})
    assert decided.status_code==200 and decided.json()['status']=='approved'
    second=client.post('/api/auth/register',json={'email':'viewer@example.test','display_name':'查看者','password':'test-password-456'})
    assert second.status_code==201,second.text
    client.post('/api/auth/login',json={'email':'owner@example.test','password':'test-password-123'})
    added=client.post(f'/api/workspaces/{workspace_id}/members',json={'email':'viewer@example.test','role':'viewer'})
    assert added.status_code==201,added.text
    client.post('/api/auth/login',json={'email':'viewer@example.test','password':'test-password-456'})
    assert client.get('/api/objects',headers={'X-Workspace-ID':workspace_id}).status_code==200
    assert client.post('/api/objects',headers={'X-Workspace-ID':workspace_id},json={'title':'禁止写入'}).status_code==403

def test_unicode_search_revision_conflict_archive(client):
    item=create(client)
    assert client.get('/api/objects?q=机器人').json()[0]['id']==item['id']
    update={**item,'title':'新的标题'}
    saved=client.patch(f"/api/objects/{item['id']}",json=update)
    assert saved.status_code==200,saved.text
    assert saved.json()['version']==2
    assert client.patch(f"/api/objects/{item['id']}",json=update).status_code==409
    revision=client.get(f"/api/objects/{item['id']}/revisions").json()[0]
    assert revision['snapshot']['tags']==['VLA','机器人']
    assert revision['snapshot']['title']=='机器人动作'
    archived={**saved.json(),'archived_at':'2026-10-01T00:00:00Z'}
    assert client.patch(f"/api/objects/{item['id']}",json=archived).status_code==200
    assert client.get('/api/objects').json()==[]
    assert len(client.get('/api/objects?archived=true').json())==1
    restored={**client.get(f"/api/objects/{item['id']}").json(),'archived_at':None}
    assert client.patch(f"/api/objects/{item['id']}",json=restored).status_code==200
    assert len(client.get('/api/objects').json())==1

def test_relation_evidence_undirected_uniqueness_graph(client):
    a,b=create(client,'VLA'),create(client,'动作表示')
    data={'source_id':a['id'],'target_id':b['id'],'relation_type':'compares_with','evidence':[{'evidence_object_id':b['id'],'locator':'第 2 节'}]}
    response=client.post('/api/relations',json=data)
    assert response.status_code==201,response.text
    assert client.post('/api/relations',json={**data,'source_id':b['id'],'target_id':a['id']}).status_code==409
    graph=client.get(f"/api/graph?center={a['id']}&depth=1").json()
    assert len(graph['nodes'])==2 and len(graph['edges'])==1
    relation=client.get('/api/relations').json()[0]
    assert relation['evidence'][0]['locator']=='第 2 节'
    update={**relation,'relation_type':'depends_on'}
    assert client.patch(f"/api/relations/{relation['id']}",json=update).status_code==200
    assert client.patch(f"/api/relations/{relation['id']}",json=update).status_code==409

def test_canvas_independence_atomicity_versions_and_detach(client):
    a,b=create(client,'模型'),create(client,'基础')
    relation=client.post('/api/relations',json={'source_id':a['id'],'target_id':b['id'],'relation_type':'depends_on'}).json()
    canvas=client.post('/api/canvases',json={'title':'第一张画布'}).json()
    items=[canvas_item(a['id']),canvas_item(b['id'],300)]
    edge={'id':str(uuid4()),'source_item_id':items[0]['id'],'target_item_id':items[1]['id'],'relation_id':relation['id'],'label':'依赖'}
    doc={'title':canvas['title'],'version':1,'viewport':{'x':10,'y':20,'zoom':0.8},'items':items,'edges':[edge]}
    response=client.put(f"/api/canvases/{canvas['id']}/document",json=doc)
    assert response.status_code==200,response.text
    assert client.put(f"/api/canvases/{canvas['id']}/document",json=doc).status_code==409
    bad={**doc,'version':2,'items':[items[0]]}
    assert client.put(f"/api/canvases/{canvas['id']}/document",json=bad).status_code==422
    stored=client.get(f"/api/canvases/{canvas['id']}").json()
    assert len(stored['items'])==2 and stored['version']==2
    other=client.post('/api/canvases',json={'title':'第二张画布'}).json()
    other_doc={**doc,'title':other['title'],'items':[canvas_item(a['id'],900)],'edges':[]}
    assert client.put(f"/api/canvases/{other['id']}/document",json=other_doc).status_code==200
    assert client.get(f"/api/canvases/{canvas['id']}").json()['viewport']['x']==10
    assert client.delete(f"/api/relations/{relation['id']}").status_code==200
    detached=client.get(f"/api/canvases/{canvas['id']}").json()['edges'][0]
    assert detached['relation_id']==relation['id'] and detached['relation_deleted'] is True
    assert client.post(f"/api/trash/relation/{relation['id']}/restore").status_code==200
    assert client.get(f"/api/canvases/{canvas['id']}").json()['edges'][0]['relation_deleted'] is False

def test_group_parent_validation_and_cycle(client):
    obj=create(client)
    canvas=client.post('/api/canvases',json={'title':'分组'}).json()
    group={'id':str(uuid4()),'item_type':'group','x':0,'y':0}
    item=canvas_item(obj['id'],parent_id=group['id'])
    doc={'title':'分组','version':1,'viewport':{'x':0,'y':0,'zoom':1},'items':[item,group],'edges':[]}
    response=client.put(f"/api/canvases/{canvas['id']}/document",json=doc)
    assert response.status_code==200,response.text
    doc['version']=2
    doc['items'][1]['parent_id']=item['id']
    assert client.put(f"/api/canvases/{canvas['id']}/document",json=doc).status_code==422

def test_sessions_and_run_validation(client):
    a=create(client)
    session=client.post('/api/sessions',json={'objective':'理解动作单位','object_ids':[a['id']],'understanding_change_md':'从关节角度区分末端位姿。'})
    assert session.status_code==201
    assert client.get('/api/sessions').json()[0]['object_ids']==[a['id']]
    assert client.post('/api/runs',json={'experiment_id':a['id']}).status_code==422
    experiment=create(client,'部署实测','experiment')
    run=client.post('/api/runs',json={'experiment_id':experiment['id'],'status':'failed','metrics':{'peak_vram_mb':1234},'artifacts':[{'location':'experiments/result.log'}]} )
    assert run.status_code==201,run.text
    assert client.get('/api/runs').json()[0]['artifacts'][0]['location']=='experiments/result.log'
    assert client.patch(f"/api/runs/{run.json()['id']}",json={**run.json(),'status':'succeeded','result_md':'运行完成'}).status_code==200

def test_learning_path_publish_share_and_revoke(client):
    concept=create(client,'VLA 基础')
    created=client.post('/api/learning-paths',json={
        'title':'VLA 入门路径',
        'steps':[{'object_id':concept['id'],'title':'理解 VLA 基础'}],
    })
    assert created.status_code==201,created.text
    path=created.json()
    assert client.post(f"/api/learning-paths/{path['id']}/publish").status_code==422
    saved=client.put(f"/api/learning-paths/{path['id']}",json={
        **path,
        'objective_md':'能够解释视觉、语言与动作之间的关系。',
        'completion_criteria_md':'能够独立画出端到端数据流。',
        'steps':[{**path['steps'][0],'completion_criteria_md':'不看笔记解释输入和输出。'}],
    })
    assert saved.status_code==200,saved.text
    published=client.post(f"/api/learning-paths/{path['id']}/publish")
    assert published.status_code==200,published.text
    token=published.json()['share_token']
    shared=client.get(f'/api/shared/learning-paths/{token}')
    assert shared.status_code==200 and shared.json()['steps'][0]['object_available'] is True
    assert client.post(f"/api/learning-paths/{path['id']}/unpublish").status_code==200
    assert client.get(f'/api/shared/learning-paths/{token}').status_code==404
    assert client.delete(f"/api/learning-paths/{path['id']}").status_code==200
    assert any(row['kind']=='path' for row in client.get('/api/trash').json())
    assert client.post(f"/api/trash/path/{path['id']}/restore").status_code==200

def test_backup_complete_roundtrip_and_conflict(client,monkeypatch,tmp_path):
    a,b=create(client,'模型'),create(client,'论文','resource')
    client.patch(f"/api/objects/{a['id']}",json={**a,'title':'模型修订'})
    relation=client.post('/api/relations',json={'source_id':a['id'],'target_id':b['id'],'relation_type':'uses','evidence':[{'evidence_object_id':b['id'],'locator':'第 3 页'}]}).json()
    canvas=client.post('/api/canvases',json={'title':'恢复布局'}).json()
    items=[canvas_item(a['id']),canvas_item(b['id'],400)]
    doc={'title':'恢复布局','version':1,'viewport':{'x':23,'y':48,'zoom':0.7},'items':items,'edges':[{'id':str(uuid4()),'source_item_id':items[0]['id'],'target_item_id':items[1]['id'],'label':'使用','relation_id':relation['id']}]}
    assert client.put(f"/api/canvases/{canvas['id']}/document",json=doc).status_code==200
    client.post('/api/sessions',json={'objective':'备份测试','object_ids':[a['id']]})
    experiment=create(client,'备份中的实验','experiment')
    client.post('/api/runs',json={'experiment_id':experiment['id'],'status':'planned','config':{'batch':1},'metrics':{'test_metric':42},'artifacts':[{'location':'external/result.log'}]})
    content='附件中文内容'.encode()
    upload=client.post(f"/api/objects/{a['id']}/attachments",files={'file':('notes.txt',content,'text/plain')})
    assert upload.status_code==201,upload.text
    assert client.delete(f"/api/relations/{relation['id']}").status_code==200
    exported=client.get('/api/export')
    assert exported.status_code==200,exported.text
    files={'file':('backup.zip',exported.content,'application/zip')}
    assert client.post('/api/import?dry_run=true',files=files).json()['conflicts']['objects']==3
    assert client.post('/api/import?dry_run=false',files=files).status_code==409
    target='test_'+uuid4().hex
    with psycopg2.connect(DSN) as connection:
        with connection.cursor() as cursor:
            migrate_schema(cursor,target)
    original_schema=workspace.SCHEMA
    original_storage=workspace.STORAGE
    monkeypatch.setattr(workspace,'SCHEMA',target)
    destination=tmp_path/'restored'
    (destination/'attachments').mkdir(parents=True)
    monkeypatch.setattr(workspace,'STORAGE',destination)
    try:
        registered=client.post('/api/auth/register',json={'email':'restore@example.test','display_name':'恢复用户','password':'restore-password-123'})
        assert registered.status_code==201,registered.text
        preview=client.post('/api/import?dry_run=true',files=files)
        assert preview.status_code==200 and preview.json()['conflicts']=={}
        restored=client.post('/api/import?dry_run=false',files=files)
        assert restored.status_code==200,restored.text
        assert client.get(f"/api/objects/{a['id']}").json()['title']=='模型修订'
        assert client.get(f"/api/attachments/{upload.json()['id']}").content==content
        assert client.get(f"/api/canvases/{canvas['id']}").json()['viewport']['x']==23
        assert any(row['id']==relation['id'] for row in client.get('/api/trash').json())
        assert client.post(f"/api/trash/relation/{relation['id']}/restore").status_code==200
        assert client.get('/api/relations').json()[0]['evidence'][0]['locator']=='第 3 页'
        assert len(client.get('/api/sessions').json())==1
        restored_run=client.get('/api/runs').json()[0]
        assert restored_run['metrics']['test_metric']==42
        assert restored_run['artifacts'][0]['location']=='external/result.log'
        assert len(client.get(f"/api/objects/{a['id']}/revisions").json())==1
        assert len(client.get(f"/api/canvases/{canvas['id']}/revisions").json())==1
    finally:
        monkeypatch.setattr(workspace,'SCHEMA',original_schema)
        monkeypatch.setattr(workspace,'STORAGE',original_storage)
        with psycopg2.connect(DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(target)))

def test_malformed_backup_and_attachment_integrity(client):
    assert client.post('/api/import',files={'file':('bad.zip',b'invalid')}).status_code==422
    a=create(client)
    client.post(f"/api/objects/{a['id']}/attachments",files={'file':('file.txt',b'original')})
    source=zipfile.ZipFile(io.BytesIO(client.get('/api/export').content))
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        for name in source.namelist():
            archive.writestr(name,b'tampered' if name.startswith('attachments/') else source.read(name))
    assert client.post('/api/import',files={'file':('tampered.zip',output.getvalue())}).status_code==422
    assert len(client.get('/api/objects').json())==1

def test_edit_and_recover_records_preserves_references(client):
    a,b=create(client,'待删除节点'),create(client,'关联节点')
    relation=client.post('/api/relations',json={'source_id':a['id'],'target_id':b['id'],'relation_type':'uses','evidence':[{'source_url':'https://example.com','locator':'第2页'}]}).json()
    canvas=client.post('/api/canvases',json={'title':'原画布'}).json()
    renamed=client.patch(f"/api/canvases/{canvas['id']}",json={'title':'新画布','version':1})
    assert renamed.status_code==200 and renamed.json()['version']==2
    assert client.patch(f"/api/canvases/{canvas['id']}",json={'title':'覆盖','version':1}).status_code==409
    item=canvas_item(a['id'])
    doc={'title':'新画布','version':2,'items':[item],'edges':[]}
    assert client.put(f"/api/canvases/{canvas['id']}/document",json=doc).status_code==200
    attachment=client.post(f"/api/objects/{a['id']}/attachments",files={'file':('original.txt',b'preserved','text/plain')}).json()
    assert client.patch(f"/api/attachments/{attachment['id']}",json={'original_name':'renamed.txt'}).json()['original_name']=='renamed.txt'
    session=client.post('/api/sessions',json={'objective':'学习原目标','object_ids':[a['id']]}).json()
    update={**session,'objective':'修改目标','object_ids':[b['id']],'occurred_at':'2026-09-30T08:00:00Z'}
    assert client.patch(f"/api/sessions/{session['id']}",json=update).status_code==200
    assert client.patch(f"/api/sessions/{session['id']}",json=update).status_code==409
    assert client.get('/api/sessions').json()[0]['object_ids']==[b['id']]
    for kind,path,record in [('attachment','attachments',attachment),('session','sessions',session),('canvas','canvases',canvas),('object','objects',a)]:
        assert client.delete(f"/api/{path}/{record['id']}").status_code==200
        assert any(row['id']==record['id'] and row['kind']==kind for row in client.get('/api/trash').json())
    assert client.get(f"/api/objects/{a['id']}").status_code==404
    assert client.get('/api/relations').json()==[]
    assert len(client.get('/api/graph').json()['nodes'])==1
    for kind,record in [('object',a),('canvas',canvas),('attachment',attachment),('session',session)]:
        assert client.post(f"/api/trash/{kind}/{record['id']}/restore").status_code==200
    assert client.get(f"/api/canvases/{canvas['id']}").json()['items'][0]['object_id']==a['id']
    assert client.get('/api/relations').json()[0]['evidence'][0]['locator']=='第2页'
    assert client.get(f"/api/attachments/{attachment['id']}").content==b'preserved'
    assert client.get('/api/trash').json()==[]

def test_run_delete_restore_parent_and_version_conflicts(client):
    experiment=create(client,'实验','experiment')
    run=client.post('/api/runs',json={'experiment_id':experiment['id'],'artifacts':[{'location':'one.log'},{'location':'two.log'}]}).json()
    update={**run,'result_md':'新结果'}
    assert client.patch(f"/api/runs/{run['id']}",json=update).status_code==200
    assert client.patch(f"/api/runs/{run['id']}",json=update).status_code==409
    assert client.delete(f"/api/runs/{run['id']}").status_code==200
    assert client.delete(f"/api/objects/{experiment['id']}").status_code==200
    assert client.get('/api/runs').json()==[]
    assert client.post(f"/api/trash/run/{run['id']}/restore").status_code==409
    assert client.post(f"/api/trash/object/{experiment['id']}/restore").status_code==200
    assert client.post(f"/api/trash/run/{run['id']}/restore").status_code==200
    restored=client.get('/api/runs').json()[0]
    assert restored['result_md']=='新结果' and len(restored['artifacts'])==2

def test_permanent_object_delete_cleans_references_and_files(client):
    a,b=create(client,'永久删除对象','experiment'),create(client,'保留对象')
    relation=client.post('/api/relations',json={'source_id':a['id'],'target_id':b['id'],'relation_type':'uses'}).json()
    other_relation=client.post('/api/relations',json={'source_id':b['id'],'target_id':create(client,'第三节点')['id'],'relation_type':'uses','evidence':[{'evidence_object_id':a['id']},{'evidence_object_id':a['id'],'source_url':'https://example.com'}]}).json()
    canvas=client.post('/api/canvases',json={'title':'保留布局'}).json()
    items=[canvas_item(a['id']),canvas_item(b['id'],300)]
    doc={'title':'保留布局','version':1,'items':items,'edges':[{'id':str(uuid4()),'source_item_id':items[0]['id'],'target_item_id':items[1]['id'],'relation_id':relation['id']}]}
    assert client.put(f"/api/canvases/{canvas['id']}/document",json=doc).status_code==200
    attachment=client.post(f"/api/objects/{a['id']}/attachments",files={'file':('delete.txt',b'content')}).json()
    file_path=workspace.STORAGE/attachment['relative_path']
    session=client.post('/api/sessions',json={'objective':'保留学习','object_ids':[a['id'],b['id']]}).json()
    run=client.post('/api/runs',json={'experiment_id':a['id']}).json()
    assert client.delete(f"/api/trash/object/{a['id']}").status_code==404
    assert file_path.exists()
    assert client.delete(f"/api/objects/{a['id']}").status_code==200
    response=client.delete(f"/api/trash/object/{a['id']}")
    assert response.status_code==200,response.text
    assert not file_path.exists()
    assert client.post(f"/api/trash/object/{a['id']}/restore").status_code==404
    stored=client.get(f"/api/canvases/{canvas['id']}").json()
    placeholder=next(item for item in stored['items'] if item['item_type']=='text')
    assert placeholder['object_id'] is None
    assert stored['edges'][0]['relation_id'] is None
    assert stored['version']==3
    assert client.get('/api/sessions').json()[0]['object_ids']==[b['id']]
    remaining=client.get('/api/relations').json()[0]
    assert remaining['id']==other_relation['id'] and len(remaining['evidence'])==1
    assert remaining['evidence'][0]['evidence_object_id'] is None
    assert client.get('/api/runs').json()==[]
    assert client.get('/api/export').status_code==200

@pytest.mark.parametrize('kind,path',[('canvas','canvases'),('session','sessions'),('run','runs'),('attachment','attachments'),('relation','relations')])
def test_permanent_record_delete(client,kind,path):
    obj=create(client,'测试父对象','experiment')
    payloads={'canvas':{'title':'删除画布'},'session':{'objective':'删除日志'},'run':{'experiment_id':obj['id']},'relation':{'source_id':obj['id'],'target_id':create(client,'目标')['id'],'relation_type':'uses'}}
    if kind=='attachment':
        record=client.post(f"/api/objects/{obj['id']}/attachments",files={'file':('delete.txt',b'content')}).json()
    else:
        record=client.post(f'/api/{path}',json=payloads[kind]).json()
    assert client.delete(f"/api/{path}/{record['id']}").status_code==200
    assert client.delete(f"/api/trash/{kind}/{record['id']}").status_code==200
    assert client.post(f"/api/trash/{kind}/{record['id']}/restore").status_code==404
    assert not any(row['id']==record['id'] for row in client.get('/api/trash').json())
    assert client.get(f"/api/objects/{obj['id']}").status_code==200

def test_invalid_reference_rolls_back_complete_import(client):
    item=create(client)
    exported=zipfile.ZipFile(io.BytesIO(client.get('/api/export').content))
    manifest=json.loads(exported.read('manifest.json'))
    manifest['tables']['objects'][0]['id']=str(uuid4())
    manifest['tables']['object_tags'][0]['object_id']=str(uuid4())
    # Remove tag IDs to avoid an early existing-ID conflict, leaving an invalid FK.
    manifest['tables']['tags']=[]
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('manifest.json',json.dumps(manifest))
    response=client.post('/api/import?dry_run=false',files={'file':('invalid.zip',output.getvalue())})
    assert response.status_code==409,response.text
    assert len(client.get('/api/objects').json())==1


def test_pdf_import_commits_images_original_and_body_references_with_backup(client):
    from backend.tests.test_import_assets import pdf_bytes
    preview=client.post('/api/source-imports/preview-file',files={'file':('figures.pdf',pdf_bytes(),'application/pdf')})
    assert preview.status_code==200,preview.text
    data=preview.json()
    assert {asset['kind'] for asset in data['assets']}=={'source','image','page'}
    assert client.get('/api/objects').json()==[]
    payload={'source_type':'pdf','source_key':data['source_key'],'preview_token':data['preview_token'],
             'object':{'kind':'resource','title':'PDF image import','body_md':data['body_md'],'metadata':data['metadata']}}
    saved=client.post('/api/source-imports/commit',json=payload)
    assert saved.status_code==201,saved.text
    item=saved.json()
    assert 'import-asset://' not in item['body_md']
    attachments=client.get(f"/api/objects/{item['id']}/attachments").json()
    assert len(attachments)==3
    for asset in attachments:
        image=client.get(f"/api/attachments/{asset['id']}/content")
        assert image.status_code==200
        assert image.headers['content-disposition'].startswith('inline')
        if asset['mime_type']=='image/png':
            assert image.content.startswith(b'\x89PNG')
            assert f"/api/attachments/{asset['id']}/content" in item['body_md']
    assert client.get(data['assets'][0]['preview_url']).status_code==404
    assert client.post('/api/source-imports/commit',json={**payload,'preview_token':None}).status_code==409
    archive=zipfile.ZipFile(io.BytesIO(client.get('/api/export').content))
    manifest=json.loads(archive.read('manifest.json'))
    assert len(manifest['tables']['attachments'])==3
    for attachment in attachments:
        assert archive.read(attachment['relative_path'])
    assert manifest['tables']['objects'][0]['body_md']==item['body_md']


def test_trashed_zotero_source_can_be_reimported_without_overwriting_old_material(client):
    payload={'source_type':'mcp','source_key':'zotero:local:0:ABCD1234',
        'object':{'kind':'resource','title':'Original paper','body_md':'Original preserved text'}}
    first=client.post('/api/source-imports/commit',json=payload).json()
    conflict=client.post('/api/source-imports/commit',json=payload)
    assert conflict.status_code==409
    assert conflict.json()['detail']['existing_import']['id']==first['id']
    note=client.post('/api/source-imports/commit',json={**payload,'save_as_note':True,
        'object':{**payload['object'],'body_md':'LLM findings\n\nOriginal preserved text'}})
    assert note.status_code==201,note.text
    assert note.json()['metadata']['derived_source']['object_id']==first['id']
    assert client.get(f"/api/objects/{first['id']}").json()['body_md']=='Original preserved text'
    assert client.delete(f"/api/objects/{first['id']}").status_code==200
    assert client.get('/api/trash').json()
    reimport=client.post('/api/source-imports/commit',json=payload)
    assert reimport.status_code==201,reimport.text
    assert reimport.json()['id']!=first['id']
    assert any(x['id']==first['id'] for x in client.get('/api/trash').json())
    assert client.post('/api/source-imports/commit',json=payload).status_code==409
