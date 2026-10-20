"""Import the reviewed research bundle through the local workspace API.

Reruns reuse research keys, never overwrite user edits, and keep existing notes.
"""
import hashlib
import io
import json
import urllib.request
from pathlib import Path
from uuid import uuid4
import zipfile

ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8001/api'
def api(path,data=None,method='GET'):
    payload=json.dumps(data,ensure_ascii=False).encode('utf-8') if data is not None else None
    request=urllib.request.Request(BASE+path,data=payload,method=method,headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(request,timeout=45))

if __name__=='__main__':
    bundle=json.loads((ROOT/'bundle.json').read_text(encoding='utf-8'))
    report_path=ROOT/'workspace-import.json'
    report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {'objects':{},'relations':{},'created_ids':[]}
    backup=Path(__file__).resolve().parents[2]/'storage/exports/pre-unitree-group-01.zip'
    if not backup.exists():
        backup.parent.mkdir(parents=True,exist_ok=True)
        data=urllib.request.urlopen(BASE+'/export',timeout=45).read()
        zipfile.ZipFile(io.BytesIO(data)).testzip()
        backup.write_bytes(data)
    existing=api('/objects?limit=1000&archived=true')
    by_key={o['metadata'].get('research_key'):o for o in existing if o['metadata'].get('research_group')==bundle['group']}
    for item in bundle['objects']:
        payload={key:value for key,value in item.items() if key!='key'}
        current=by_key.get(item['key'])
        if not current and item['key'] in ['model:wma','repo:wma']:
            current=next((o for o in existing if o['kind']==item['kind'] and (o['title']==item['title'] or o.get('source_url')==item['source_url'])),None)
            if current:
                # Preserve original content and attach research, rather than replacing it.
                payload['body_md']=current['body_md']+'\n\n---\n\n## 第一组研究补充（Research Supplement）\n\n'+item['body_md']
                payload['metadata']={**current['metadata'],**item['metadata']}
                payload['tags']=list(dict.fromkeys(current['tags']+item['tags']))
                payload['version']=current['version']
                payload['archived_at']=current['archived_at']
                payload['reading_status']=current['reading_status']
                payload['mastery_status']=current['mastery_status']
                current=api('/objects/'+current['id'],payload,'PATCH')
        if not current:
            current=api('/objects',payload,'POST')
            report['created_ids'].append(current['id'])
        report['objects'][item['key']]=current['id']
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    current_relations=api('/relations')
    def relation_key(source,target,kind):
        if kind in ['related_to','compares_with']: source,target=sorted([source,target])
        return source,target,kind
    existing_relations={relation_key(row['source_id'],row['target_id'],row['relation_type']):row for row in current_relations}
    for index,relation in enumerate(bundle['relations']):
        a=report['objects'][relation['source_key']];b=report['objects'][relation['target_key']]
        key=relation_key(a,b,relation['relation_type'])
        payload={k:v for k,v in relation.items() if k not in ['source_key','target_key']}
        payload.update(source_id=a,target_id=b)
        current=existing_relations.get(key)
        if not current:
            current=api('/relations',payload,'POST')
            existing_relations[key]=current
        elif not current.get('evidence') and payload['evidence']:
            current=api('/relations/'+current['id'],{**current,'evidence':payload['evidence']},'PATCH')
        report['relations'][str(index)]=current['id']
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

    title='第一组：宇树模型谱系与学习路径（Unitree Study Map）'
    canvas=next((c for c in api('/canvases') if c['title']==title),None)
    if not canvas:
        canvas=api('/canvases',{'title':title},'POST')
        layout=[
          ('hub',760,-270),('comparison',1100,-270),
          ('base:dynamic',0,0),('base:vlm',570,0),('base:qwen3',1450,0),
          ('model:wma',0,280),('model:vla',570,280),('model:er1',1120,280),('model:flow',1450,280),('model:wla',1780,280),
          ('concept:latent',0,570),('concept:fm',570,570),('concept:flowmask',1120,570),('concept:vq',1450,570),('concept:mmdit',1780,570),
          ('task:01',0,900),('task:02',350,900),('task:03',700,900),('task:04',1050,900),('task:05',1400,900),('task:06',1750,900),
          ('actions',350,1200),('gaps',700,1200),('runbook',1050,1200),('budget',1400,1200),('fusion',1750,1200)]
        note_by_key={o['key']:o for o in bundle['objects']}
        items=[{'id':str(uuid4()),'object_id':report['objects'][key],'item_type':'object','x':x,'y':y,'width':300,'height':210,'properties':{}} for key,x,y in layout]
        item_ids={layout[i][0]:item['id'] for i,item in enumerate(items)}
        canvas_edges=[]
        selected=[('model:wma','base:dynamic'),('model:vla','base:vlm'),('model:er1','base:qwen3'),('model:flow','model:er1'),('model:wla','model:flow'),('model:wma','concept:latent'),('model:vla','concept:fm'),('model:flow','concept:flowmask'),('model:flow','concept:vq'),('model:wla','concept:mmdit')]
        selected+=[(tasks,tprev) for tasks,tprev in [('task:02','task:01'),('task:03','task:02'),('task:04','task:03'),('task:05','task:04'),('task:06','task:05')]]
        for a,b in selected:
            relation=next((r for r in bundle['relations'] if r['source_key']==a and r['target_key']==b),None)
            if relation:
                idx=bundle['relations'].index(relation)
                canvas_edges.append({'id':str(uuid4()),'source_item_id':item_ids[a],'target_item_id':item_ids[b],'relation_id':report['relations'][str(idx)],'label':{'depends_on':'基座／前置（Depends on）','uses':'使用（Uses）'}.get(relation['relation_type'],'关联（Related）')})
        # Reading direction is an explicit local guide, separate from semantic relations.
        for a,b in [('hub','comparison'),('task:02','actions'),('task:05','runbook'),('runbook','budget'),('task:06','gaps')]:
            canvas_edges.append({'id':str(uuid4()),'source_item_id':item_ids[a],'target_item_id':item_ids[b],'relation_id':None,'label':'阅读入口（Read next）'})
        api('/canvases/'+canvas['id']+'/document',{'title':title,'version':canvas['version'],'viewport':{'x':18,'y':105,'zoom':0.30},'items':items,'edges':canvas_edges},'PUT')
    report['canvas_id']=canvas['id']
    runs=api('/runs')
    report['planned_runs']=[]
    for key in ['exp:er','exp:wma','exp:wla']:
        identifier=report['objects'][key]
        run=next((r for r in runs if r['experiment_id']==identifier),None)
        if not run:
            model={'exp:er':'UnifoLM-ER-1','exp:wma':'UnifoLM-WMA-0','exp:wla':'UnifoLM-WLA-1.0'}[key]
            run=api('/runs',{'experiment_id':identifier,'status':'planned','hypothesis_md':'计划验证 '+model+' 的离线输入输出与本机资源需求；尚未执行。','config':{'research_group':bundle['group'],'execution_status':'not_started','gpu':'RTX4090','robot_available':False},'environment':{'os':'Windows; Linux/WSL2 environment to verify'},'metrics':{},'result_md':'','failure_md':'','artifacts':[]},'POST')
        report['planned_runs'].append(run['id'])
    sessions=api('/sessions')
    objective='第一组宇树研究：资料核对与学习路径建立（Source Audit and Study Setup）'
    session=next((s for s in sessions if s['objective']==objective),None)
    if not session:
        session=api('/sessions',{'objective':objective,'activity_md':'由助手核对官方发布、固定版本源码与模型文件元数据，整理60个条目与91条关系，建立学习画布与待运行实验。此记录仅代表资料整理，不代表用户已学完。','understanding_change_md':'已明确视频预测、具身推理、动态区域离散表征与连续动作专家的区别；待用户完成任务01后补写自己的理解。','blockers_md':'GPU推理尚未执行；需要盘点Linux/WSL2环境；VLA常量与发布配置、ER-Flow解码器公开边界仍需复现核验。','next_step_md':'完成任务01的五模型输入／输出表，随后学习统一动作空间。','object_ids':[report['objects'][key] for key in ['hub','comparison','gaps','task:01']]},'POST')
    report['session_id']=session['id']
    report['verified_on']=bundle['verified_on']
    report['backup_path']=str(backup)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    # Read-back verifies real storage, not merely success messages.
    for key,identifier in report['objects'].items():
        stored=api('/objects/'+identifier)
        assert stored['metadata']['research_key']==key
        assert stored['body_md'].strip()
    graph=api('/graph')
    assert set(report['objects'].values()).issubset({row['id'] for row in graph['nodes']})
    assert set(report['relations'].values()).issubset({row['id'] for row in graph['edges']})
    stored_canvas=api('/canvases/'+canvas['id'])
    assert len(stored_canvas['items'])==26
    print(json.dumps({'research_objects':len(report['objects']),'research_relations':len(report['relations']),'canvas_cards':len(stored_canvas['items']),'planned_runs':len(report['planned_runs']),'hub_url':'http://127.0.0.1:5174/knowledge/'+report['objects']['hub'],'canvas_url':'http://127.0.0.1:5174/canvases/'+canvas['id']},ensure_ascii=False))
