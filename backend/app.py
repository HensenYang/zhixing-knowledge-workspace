"""Local personal knowledge workspace. PostgreSQL is the source of truth."""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4
import hashlib
import io
import json
import os
import re
import shutil
import zipfile

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

from .exporters import material_docx, material_markdown, material_pdf
from .importers import import_locator, import_pdf

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(Path(os.environ.get('WORKSPACE_ENV_FILE', str(ROOT / '.env'))))
STORAGE = Path(os.environ.get('STORAGE_ROOT', 'storage'))
if not STORAGE.is_absolute():
    STORAGE = ROOT / STORAGE
STORAGE.mkdir(parents=True, exist_ok=True)
(STORAGE / 'attachments').mkdir(exist_ok=True)
SCHEMA = os.environ.get('KNOWLEDGE_SCHEMA', 'knowledge')
app = FastAPI(title='Embodied Knowledge Workspace', version='0.1.0')

Kind = Literal['concept','resource','repository','model','dataset','benchmark','experiment','question','task']
RelationType = Literal['depends_on','implements','uses','evaluates','supports','questions','compares_with','related_to']
TRASH_TABLES = {'object':'objects','relation':'relations','canvas':'canvases',
                'session':'learning_sessions','run':'experiment_runs','attachment':'attachments'}

@contextmanager
def db():
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise HTTPException(503, '数据库尚未配置，请在本机运行 scripts/setup_database.ps1。')
    connection = None
    try:
        connection = psycopg2.connect(dsn, connect_timeout=5)
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql.SQL('SET LOCAL search_path TO {}, public').format(sql.Identifier(SCHEMA)))
                yield cursor
    except psycopg2.IntegrityError:
        raise HTTPException(409, '存在重复记录或无效引用，修改未保存。')
    except psycopg2.OperationalError:
        raise HTTPException(503, '无法连接 PostgreSQL，请检查本地服务与 .env 配置。')
    except psycopg2.ProgrammingError:
        raise HTTPException(503, '数据库结构未就绪，请运行 scripts/migrate.py。')
    finally:
        if connection is not None:
            connection.close()

def require(cursor, table, identifier):
    active = sql.SQL(' AND deleted_at IS NULL') if table in TRASH_TABLES.values() else sql.SQL('')
    cursor.execute(sql.SQL('SELECT * FROM {} WHERE id=%s{}').format(sql.Identifier(table),active), (str(identifier),))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(404, '记录不存在。')
    return row

def json_value(value):
    return Json(jsonable_encoder(value))

class ObjectInput(BaseModel):
    kind: Kind = 'concept'
    title: str = Field(min_length=1, max_length=500)
    summary: str = ''
    body_md: str = ''
    source_url: str | None = None
    reading_status: Literal['unread','skimming','reading','organized'] = 'unread'
    mastery_status: Literal['unknown','explain','implement','reproduce','analyze'] = 'unknown'
    metadata: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

class ObjectUpdate(ObjectInput):
    version: int = Field(ge=1)
    archived_at: datetime | None = None

SourceType = Literal['auto','arxiv','doi','github','mcp']

class SourcePreviewInput(BaseModel):
    source: str = Field(min_length=1,max_length=4000)
    source_type: SourceType = 'auto'

class SourceImportCommit(BaseModel):
    source_type: Literal['arxiv','doi','github','pdf','mcp']
    source_key: str = Field(min_length=1,max_length=1000)
    extracted_metadata: dict = Field(default_factory=dict)
    object: ObjectInput

def validate_object(data):
    if not data.title.strip():
        raise HTTPException(422, '标题不能为空。')
    if data.kind == 'resource' and data.metadata.get('subtype', 'paper') not in ['paper','blog','course','documentation']:
        raise HTTPException(422, '资料子类型无效。')
    for key in ['commit','weight_version','doi','arxiv','acceptance','inputs','outputs']:
        if key in data.metadata and not isinstance(data.metadata[key], str):
            raise HTTPException(422, f'{key} 必须是文本。')

def set_tags(cursor, identifier, tags):
    cursor.execute('DELETE FROM object_tags WHERE object_id=%s', (str(identifier),))
    for name in sorted({tag.strip() for tag in tags if tag.strip()}):
        cursor.execute('INSERT INTO tags(name) VALUES (%s) ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING id', (name,))
        tag_id = cursor.fetchone()['id']
        cursor.execute('INSERT INTO object_tags(object_id,tag_id) VALUES (%s,%s)', (str(identifier),tag_id))

def object_with_tags(cursor, row):
    cursor.execute('SELECT name FROM tags JOIN object_tags ON tags.id=tag_id WHERE object_id=%s ORDER BY name', (row['id'],))
    return {**row, 'tags':[tag['name'] for tag in cursor.fetchall()]}

def add_duplicate_hints(preview):
    with db() as cursor:
        cursor.execute('''SELECT id,title,source_url FROM objects WHERE deleted_at IS NULL AND
            (lower(title)=lower(%s) OR (%s IS NOT NULL AND source_url=%s)) ORDER BY updated_at DESC LIMIT 5''',
            (preview['title'],preview.get('source_url'),preview.get('source_url')))
        preview['possible_duplicates'] = cursor.fetchall()
    return preview

@app.get('/api/health')
def health():
    try:
        with db() as cursor:
            cursor.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            version = cursor.fetchone()
        return {'service':'ready','database':'ready','schema_version':version['version'] if version else None}
    except HTTPException as error:
        return {'service':'ready','database':'unavailable','message':error.detail}

@app.get('/api/source-imports/providers')
def source_import_providers():
    return {
        'providers': ['arxiv','doi','github','pdf'],
        'mcp': {
            'enabled': bool(os.environ.get('MCP_IMPORT_SERVER_URL','').strip()),
            'tool': os.environ.get('MCP_IMPORT_TOOL','import_source'),
        },
    }

@app.post('/api/source-imports/preview')
async def preview_source(data: SourcePreviewInput):
    return add_duplicate_hints(await import_locator(data.source,data.source_type))

@app.post('/api/source-imports/preview-file')
async def preview_source_file(file: UploadFile = File(...)):
    content = await file.read(32 * 1024 * 1024 + 1)
    return add_duplicate_hints(import_pdf(content,Path(file.filename or 'document.pdf').name))

@app.post('/api/source-imports/commit',status_code=201)
def commit_source_import(data: SourceImportCommit):
    validate_object(data.object)
    with db() as cursor:
        cursor.execute('SELECT object_id FROM source_imports WHERE source_type=%s AND source_key=%s',
            (data.source_type,data.source_key))
        existing=cursor.fetchone()
        if existing:
            raise HTTPException(409,'该来源已经导入。请打开已有资料，或修改后使用普通新建笔记。')
        item=data.object
        cursor.execute('''INSERT INTO objects(kind,title,summary,body_md,source_url,reading_status,mastery_status,metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (item.kind,item.title.strip(),item.summary,item.body_md,item.source_url,item.reading_status,item.mastery_status,json_value(item.metadata)))
        row=cursor.fetchone()
        set_tags(cursor,row['id'],item.tags)
        cursor.execute('''INSERT INTO source_imports(source_type,source_key,source_url,original_name,extracted_metadata,object_id)
            VALUES (%s,%s,%s,%s,%s,%s)''',
            (data.source_type,data.source_key,item.source_url,data.extracted_metadata.get('file_name'),json_value(data.extracted_metadata),row['id']))
        return object_with_tags(cursor,row)

@app.get('/api/objects')
def list_objects(q: str = '', kind: str = '', archived: bool = False, limit: int = 200, offset: int = 0):
    limit = min(max(limit,1),1000)
    with db() as cursor:
        cursor.execute('''SELECT * FROM objects WHERE deleted_at IS NULL AND (%s OR archived_at IS NULL)
            AND (%s='' OR kind=%s) AND (%s='' OR title ILIKE %s OR body_md ILIKE %s OR
            EXISTS(SELECT 1 FROM object_tags ot JOIN tags t ON t.id=ot.tag_id WHERE ot.object_id=objects.id AND t.name ILIKE %s))
            ORDER BY updated_at DESC LIMIT %s OFFSET %s''', (archived,kind,kind,q,f'%{q}%',f'%{q}%',f'%{q}%',limit,max(offset,0)))
        rows = cursor.fetchall()
        return [object_with_tags(cursor,row) for row in rows]

@app.post('/api/objects', status_code=201)
def create_object(data: ObjectInput):
    validate_object(data)
    with db() as cursor:
        cursor.execute('''INSERT INTO objects(kind,title,summary,body_md,source_url,reading_status,mastery_status,metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''', (data.kind,data.title.strip(),data.summary,data.body_md,data.source_url,data.reading_status,data.mastery_status,json_value(data.metadata)))
        row = cursor.fetchone()
        set_tags(cursor,row['id'],data.tags)
        return object_with_tags(cursor,row)

@app.get('/api/objects/{identifier}')
def get_object(identifier: UUID):
    with db() as cursor:
        return object_with_tags(cursor,require(cursor,'objects',identifier))

@app.patch('/api/objects/{identifier}')
def update_object(identifier: UUID, data: ObjectUpdate):
    validate_object(data)
    with db() as cursor:
        cursor.execute('SELECT * FROM objects WHERE id=%s AND deleted_at IS NULL FOR UPDATE', (str(identifier),))
        old = cursor.fetchone()
        if not old:
            raise HTTPException(404,'记录不存在。')
        if old['version'] != data.version:
            raise HTTPException(409,'另一标签页已修改此笔记。草稿已保留，请重新加载后合并。')
        snapshot = object_with_tags(cursor,old)
        cursor.execute('INSERT INTO object_revisions(object_id,version,snapshot) VALUES (%s,%s,%s)', (str(identifier),old['version'],json_value(snapshot)))
        cursor.execute('''UPDATE objects SET kind=%s,title=%s,summary=%s,body_md=%s,source_url=%s,
            reading_status=%s,mastery_status=%s,metadata=%s,archived_at=%s,version=version+1,updated_at=now()
            WHERE id=%s RETURNING *''', (data.kind,data.title.strip(),data.summary,data.body_md,data.source_url,data.reading_status,data.mastery_status,json_value(data.metadata),data.archived_at,str(identifier)))
        row = cursor.fetchone()
        set_tags(cursor,identifier,data.tags)
        return object_with_tags(cursor,row)

@app.get('/api/objects/{identifier}/revisions')
def revisions(identifier: UUID):
    with db() as cursor:
        cursor.execute('SELECT * FROM object_revisions WHERE object_id=%s ORDER BY version DESC', (str(identifier),))
        return cursor.fetchall()

class Evidence(BaseModel):
    evidence_object_id: UUID | None = None
    source_url: str | None = None
    locator: str = ''
    explanation: str = ''

class RelationInput(BaseModel):
    source_id: UUID
    target_id: UUID
    relation_type: RelationType = 'related_to'
    description: str = ''
    evidence: list[Evidence] = Field(default_factory=list)

class RelationUpdate(RelationInput):
    version: int = Field(ge=1)

def relation_values(data):
    source,target = str(data.source_id),str(data.target_id)
    if source == target:
        raise HTTPException(422,'请选择两个不同的知识对象。')
    if data.relation_type in ['related_to','compares_with']:
        source,target = sorted([source,target])
    return source,target,data.relation_type,data.description

def save_evidence(cursor, identifier, evidence):
    cursor.execute('DELETE FROM relation_evidence WHERE relation_id=%s', (str(identifier),))
    for item in evidence:
        if item.evidence_object_id is None and not item.source_url:
            raise HTTPException(422,'证据需要对象或来源地址。')
        cursor.execute('INSERT INTO relation_evidence(relation_id,evidence_object_id,source_url,locator,explanation) VALUES (%s,%s,%s,%s,%s)', (str(identifier),str(item.evidence_object_id) if item.evidence_object_id else None,item.source_url,item.locator,item.explanation))

@app.get('/api/relations')
def list_relations():
    with db() as cursor:
        cursor.execute('''SELECT r.* FROM relations r JOIN objects a ON a.id=r.source_id
            JOIN objects b ON b.id=r.target_id WHERE r.deleted_at IS NULL
            AND a.deleted_at IS NULL AND b.deleted_at IS NULL ORDER BY r.created_at''')
        rows = cursor.fetchall()
        for row in rows:
            cursor.execute('SELECT * FROM relation_evidence WHERE relation_id=%s', (row['id'],))
            row['evidence'] = cursor.fetchall()
        return rows

@app.post('/api/relations', status_code=201)
def create_relation(data: RelationInput):
    with db() as cursor:
        require(cursor,'objects',data.source_id)
        require(cursor,'objects',data.target_id)
        cursor.execute('INSERT INTO relations(source_id,target_id,relation_type,description) VALUES (%s,%s,%s,%s) RETURNING *', relation_values(data))
        row = cursor.fetchone()
        save_evidence(cursor,row['id'],data.evidence)
        return row

@app.patch('/api/relations/{identifier}')
def update_relation(identifier: UUID, data: RelationUpdate):
    with db() as cursor:
        require(cursor,'relations',identifier)
        require(cursor,'objects',data.source_id)
        require(cursor,'objects',data.target_id)
        cursor.execute('UPDATE relations SET source_id=%s,target_id=%s,relation_type=%s,description=%s,version=version+1,updated_at=now() WHERE id=%s AND version=%s RETURNING *', (*relation_values(data),str(identifier),data.version))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(409,'关系已被修改，请重新加载。')
        cursor.execute('''UPDATE canvas_edges ce SET relation_id=NULL,
            properties=ce.properties || '{"detached":true}'::jsonb
            FROM canvas_items a,canvas_items b
            WHERE ce.relation_id=%s AND a.id=ce.source_item_id AND b.id=ce.target_item_id
            AND NOT ((a.object_id=%s AND b.object_id=%s) OR
                (%s IN ('related_to','compares_with') AND a.object_id=%s AND b.object_id=%s))''',
            (str(identifier),row['source_id'],row['target_id'],row['relation_type'],row['target_id'],row['source_id']))
        save_evidence(cursor,identifier,data.evidence)
        return row

@app.delete('/api/relations/{identifier}')
def delete_relation(identifier: UUID):
    return move_to_trash('relation', identifier)

@app.get('/api/graph')
def graph(center: UUID | None = None, depth: int = 1):
    with db() as cursor:
        cursor.execute('SELECT id,title,kind,mastery_status FROM objects WHERE archived_at IS NULL AND deleted_at IS NULL')
        nodes = cursor.fetchall()
        cursor.execute('''SELECT r.* FROM relations r JOIN objects a ON a.id=r.source_id JOIN objects b ON b.id=r.target_id
            WHERE a.archived_at IS NULL AND b.archived_at IS NULL
            AND a.deleted_at IS NULL AND b.deleted_at IS NULL AND r.deleted_at IS NULL''')
        edges = cursor.fetchall()
    if center:
        selected = {str(center)}
        for _ in range(min(max(depth,1),3)):
            neighbours = set(selected)
            for edge in edges:
                if str(edge['source_id']) in selected or str(edge['target_id']) in selected:
                    neighbours.update([str(edge['source_id']),str(edge['target_id'])])
            selected = neighbours
        nodes = [node for node in nodes if str(node['id']) in selected]
        edges = [edge for edge in edges if str(edge['source_id']) in selected and str(edge['target_id']) in selected]
    return {'nodes':nodes,'edges':edges}

class CanvasInput(BaseModel):
    title: str = Field(min_length=1)

class CanvasRename(CanvasInput):
    version: int = Field(ge=1)

class CanvasItem(BaseModel):
    id: UUID
    item_type: Literal['object','text','group']
    object_id: UUID | None = None
    parent_id: UUID | None = None
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    width: float = Field(default=260,gt=0,allow_inf_nan=False)
    height: float = Field(default=160,gt=0,allow_inf_nan=False)
    properties: dict = Field(default_factory=dict)

class CanvasEdge(BaseModel):
    id: UUID
    source_item_id: UUID
    target_item_id: UUID
    relation_id: UUID | None = None
    label: str = ''
    properties: dict = Field(default_factory=dict)

class CanvasDocument(BaseModel):
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    viewport: dict = Field(default_factory=lambda:{'x':0,'y':0,'zoom':1})
    items: list[CanvasItem] = Field(default_factory=list)
    edges: list[CanvasEdge] = Field(default_factory=list)

def canvas_document(cursor, identifier):
    row = require(cursor,'canvases',identifier)
    cursor.execute('SELECT * FROM canvas_items WHERE canvas_id=%s ORDER BY parent_id NULLS FIRST,id', (str(identifier),))
    row['items'] = cursor.fetchall()
    cursor.execute('SELECT * FROM canvas_edges WHERE canvas_id=%s', (str(identifier),))
    row['edges'] = cursor.fetchall()
    for edge in row['edges']:
        if edge['relation_id']:
            cursor.execute('SELECT deleted_at FROM relations WHERE id=%s',(edge['relation_id'],))
            linked = cursor.fetchone()
            edge['relation_deleted'] = linked is None or linked['deleted_at'] is not None
    return row

def validate_canvas(cursor, data):
    items = {str(item.id):item for item in data.items}
    if len(items) != len(data.items) or len({str(edge.id) for edge in data.edges}) != len(data.edges):
        raise HTTPException(422,'画布实例 ID 重复。')
    viewport = data.viewport
    if not all(isinstance(viewport.get(key), (float,int)) for key in ['x','y','zoom']) or viewport['zoom'] <= 0:
        raise HTTPException(422,'视口数据无效。')
    for item in data.items:
        if (item.item_type == 'object') != (item.object_id is not None):
            raise HTTPException(422,'对象卡片必须引用一个知识对象。')
        if item.object_id:
            # Existing cards may retain references to deleted objects for restoration.
            cursor.execute('SELECT id FROM objects WHERE id=%s',(str(item.object_id),))
            if not cursor.fetchone():
                raise HTTPException(422,'知识对象不存在。')
        seen = {str(item.id)}
        parent = item.parent_id
        while parent:
            parent_item = items.get(str(parent))
            if not parent_item or parent_item.item_type != 'group' or str(parent) in seen:
                raise HTTPException(422,'分组引用无效或存在循环。')
            seen.add(str(parent))
            parent = parent_item.parent_id
    for edge in data.edges:
        source,target = items.get(str(edge.source_item_id)),items.get(str(edge.target_item_id))
        if source is None or target is None or source.id == target.id:
            raise HTTPException(422,'画布连线端点无效。')
        if edge.relation_id:
            cursor.execute('SELECT * FROM relations WHERE id=%s',(str(edge.relation_id),))
            relation = cursor.fetchone()
            if not relation:
                raise HTTPException(422,'关系不存在。')
            endpoints = (str(source.object_id),str(target.object_id))
            expected = (str(relation['source_id']),str(relation['target_id']))
            if relation['relation_type'] in ['related_to','compares_with']:
                valid = set(endpoints) == set(expected)
            else:
                valid = endpoints == expected
            if not valid:
                raise HTTPException(422,'知识关系与画布对象端点不一致。')

@app.get('/api/canvases')
def list_canvases():
    with db() as cursor:
        cursor.execute('SELECT * FROM canvases WHERE deleted_at IS NULL ORDER BY updated_at DESC')
        return cursor.fetchall()

@app.post('/api/canvases', status_code=201)
def create_canvas(data: CanvasInput):
    with db() as cursor:
        cursor.execute('INSERT INTO canvases(title) VALUES (%s) RETURNING *', (data.title,))
        return cursor.fetchone()

@app.get('/api/canvases/{identifier}')
def get_canvas(identifier: UUID):
    with db() as cursor:
        return canvas_document(cursor,identifier)

@app.patch('/api/canvases/{identifier}')
def rename_canvas(identifier: UUID,data: CanvasRename):
    if not data.title.strip():
        raise HTTPException(422,'画布标题不能为空。')
    with db() as cursor:
        require(cursor,'canvases',identifier)
        old=canvas_document(cursor,identifier)
        cursor.execute('UPDATE canvases SET title=%s,version=version+1,updated_at=now() WHERE id=%s AND version=%s AND deleted_at IS NULL RETURNING *',
                       (data.title.strip(),str(identifier),data.version))
        row=cursor.fetchone()
        if not row:
            raise HTTPException(409,'画布已修改，请刷新后重试。')
        cursor.execute('INSERT INTO canvas_revisions(canvas_id,version,snapshot) VALUES (%s,%s,%s)',
                       (str(identifier),data.version,json_value(old)))
        return row

@app.put('/api/canvases/{identifier}/document')
def save_canvas(identifier: UUID, data: CanvasDocument):
    with db() as cursor:
        cursor.execute('SELECT * FROM canvases WHERE id=%s AND deleted_at IS NULL FOR UPDATE', (str(identifier),))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404,'画布不存在。')
        if row['version'] != data.version:
            raise HTTPException(409,'另一标签页已修改画布。请保留草稿并重新加载。')
        validate_canvas(cursor,data)
        old = canvas_document(cursor,identifier)
        cursor.execute('INSERT INTO canvas_revisions(canvas_id,version,snapshot) VALUES (%s,%s,%s)', (str(identifier),data.version,json_value(old)))
        cursor.execute('DELETE FROM canvas_edges WHERE canvas_id=%s', (str(identifier),))
        cursor.execute('DELETE FROM canvas_items WHERE canvas_id=%s', (str(identifier),))
        for item in data.items:
            cursor.execute('''INSERT INTO canvas_items(id,canvas_id,item_type,object_id,parent_id,x,y,width,height,properties)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (str(item.id),str(identifier),item.item_type,str(item.object_id) if item.object_id else None,str(item.parent_id) if item.parent_id else None,item.x,item.y,item.width,item.height,json_value(item.properties)))
        for edge in data.edges:
            cursor.execute('INSERT INTO canvas_edges(id,canvas_id,source_item_id,target_item_id,relation_id,label,properties) VALUES (%s,%s,%s,%s,%s,%s,%s)', (str(edge.id),str(identifier),str(edge.source_item_id),str(edge.target_item_id),str(edge.relation_id) if edge.relation_id else None,edge.label,json_value(edge.properties)))
        cursor.execute('UPDATE canvases SET title=%s,viewport=%s,version=version+1,updated_at=now() WHERE id=%s', (data.title,json_value(data.viewport),str(identifier)))
        return canvas_document(cursor,identifier)

@app.get('/api/canvases/{identifier}/revisions')
def canvas_revisions(identifier: UUID):
    with db() as cursor:
        cursor.execute('SELECT * FROM canvas_revisions WHERE canvas_id=%s ORDER BY version DESC', (str(identifier),))
        return cursor.fetchall()

class SessionInput(BaseModel):
    objective: str = Field(min_length=1)
    occurred_at: datetime | None = None
    activity_md: str = ''
    understanding_change_md: str = ''
    blockers_md: str = ''
    next_step_md: str = ''
    duration_minutes: int | None = Field(default=None,ge=0)
    object_ids: list[UUID] = Field(default_factory=list)
    version: int | None = Field(default=None,ge=1)

@app.get('/api/sessions')
def sessions():
    with db() as cursor:
        cursor.execute('SELECT * FROM learning_sessions WHERE deleted_at IS NULL ORDER BY occurred_at DESC')
        rows = cursor.fetchall()
        for row in rows:
            cursor.execute('SELECT object_id FROM session_objects WHERE session_id=%s', (row['id'],))
            row['object_ids'] = [item['object_id'] for item in cursor.fetchall()]
        return rows

@app.post('/api/sessions', status_code=201)
def create_session(data: SessionInput):
    with db() as cursor:
        for object_id in set(data.object_ids):
            require(cursor,'objects',object_id)
        cursor.execute('''INSERT INTO learning_sessions(objective,activity_md,understanding_change_md,blockers_md,next_step_md,duration_minutes,occurred_at)
            VALUES (%s,%s,%s,%s,%s,%s,COALESCE(%s,now())) RETURNING *''', (data.objective,data.activity_md,data.understanding_change_md,data.blockers_md,data.next_step_md,data.duration_minutes,data.occurred_at))
        row = cursor.fetchone()
        for object_id in set(data.object_ids):
            cursor.execute('INSERT INTO session_objects(session_id,object_id) VALUES (%s,%s)', (row['id'],str(object_id)))
        return row

@app.patch('/api/sessions/{identifier}')
def update_session(identifier: UUID,data: SessionInput):
    with db() as cursor:
        row=require(cursor,'learning_sessions',identifier)
        cursor.execute('SELECT object_id FROM session_objects WHERE session_id=%s',(str(identifier),))
        previous_ids={item['object_id'] for item in cursor.fetchall()}
        expected=data.version if data.version is not None else row['version']
        cursor.execute('''UPDATE learning_sessions SET objective=%s,activity_md=%s,understanding_change_md=%s,
            blockers_md=%s,next_step_md=%s,duration_minutes=%s,occurred_at=COALESCE(%s,occurred_at),updated_at=now(),version=version+1
            WHERE id=%s AND version=%s AND deleted_at IS NULL RETURNING *''',
            (data.objective,data.activity_md,data.understanding_change_md,data.blockers_md,data.next_step_md,
             data.duration_minutes,data.occurred_at,str(identifier),expected))
        updated=cursor.fetchone()
        if not updated:
            raise HTTPException(409,'学习记录已修改，请刷新后重试。')
        cursor.execute('DELETE FROM session_objects WHERE session_id=%s',(str(identifier),))
        for object_id in set(data.object_ids):
            if object_id not in previous_ids:
                require(cursor,'objects',object_id)
            cursor.execute('INSERT INTO session_objects(session_id,object_id) VALUES (%s,%s)',(str(identifier),str(object_id)))
        return updated

class Artifact(BaseModel):
    artifact_type: str = 'file'
    location: str = Field(min_length=1)
    sha256: str | None = None

class RunInput(BaseModel):
    experiment_id: UUID
    status: Literal['planned','running','succeeded','failed','cancelled'] = 'planned'
    hypothesis_md: str = ''
    command: str = ''
    git_commit: str | None = None
    weight_version: str | None = None
    dataset_version: str | None = None
    config: dict = Field(default_factory=dict)
    environment: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    seed: int | None = None
    result_md: str = ''
    failure_md: str = ''
    artifacts: list[Artifact] = Field(default_factory=list)
    version: int | None = Field(default=None,ge=1)

@app.get('/api/runs')
def list_runs():
    with db() as cursor:
        cursor.execute('''SELECT r.* FROM experiment_runs r JOIN objects o ON o.id=r.experiment_id
            WHERE r.deleted_at IS NULL AND o.deleted_at IS NULL ORDER BY r.created_at DESC''')
        rows = cursor.fetchall()
        for row in rows:
            cursor.execute('SELECT * FROM run_artifacts WHERE run_id=%s', (row['id'],))
            row['artifacts'] = cursor.fetchall()
        return rows

def write_run(cursor,data,identifier=None):
    if require(cursor,'objects',data.experiment_id)['kind'] != 'experiment':
        raise HTTPException(422,'运行必须关联实验对象。')
    fields = ['experiment_id','status','hypothesis_md','command','git_commit','weight_version','dataset_version','config','environment','metrics','seed','result_md','failure_md']
    values = [str(data.experiment_id) if name=='experiment_id' else json_value(getattr(data,name)) if name in ['config','environment','metrics'] else getattr(data,name) for name in fields]
    if identifier:
        old=require(cursor,'experiment_runs',identifier)
        expected=data.version if data.version is not None else old['version']
        statement = sql.SQL('UPDATE experiment_runs SET {},updated_at=now(),version=version+1 WHERE id=%s AND version=%s AND deleted_at IS NULL RETURNING *').format(sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(name)) for name in fields))
        cursor.execute(statement,(*values,str(identifier),expected))
    else:
        statement = sql.SQL('INSERT INTO experiment_runs({}) VALUES ({}) RETURNING *').format(sql.SQL(',').join(map(sql.Identifier,fields)),sql.SQL(',').join(sql.Placeholder() for _ in fields))
        cursor.execute(statement,values)
    row = cursor.fetchone()
    if not row:
        raise HTTPException(409,'实验运行已修改，请刷新后重试。')
    cursor.execute('DELETE FROM run_artifacts WHERE run_id=%s',(row['id'],))
    for artifact in data.artifacts:
        cursor.execute('INSERT INTO run_artifacts(run_id,artifact_type,location,sha256) VALUES (%s,%s,%s,%s)',(row['id'],artifact.artifact_type,artifact.location,artifact.sha256))
    cursor.execute('SELECT * FROM run_artifacts WHERE run_id=%s',(row['id'],))
    row['artifacts']=cursor.fetchall()
    return row

@app.post('/api/runs', status_code=201)
def create_run(data: RunInput):
    with db() as cursor:
        return write_run(cursor,data)

@app.patch('/api/runs/{identifier}')
def update_run(identifier: UUID,data: RunInput):
    with db() as cursor:
        return write_run(cursor,data,identifier)

def move_to_trash(kind, identifier):
    table = TRASH_TABLES[kind]
    with db() as cursor:
        row = require(cursor,table,identifier)
        version = ',version=version+1' if 'version' in row else ''
        cursor.execute(sql.SQL('UPDATE {} SET deleted_at=now()' + version + ' WHERE id=%s AND deleted_at IS NULL RETURNING *').format(sql.Identifier(table)),(str(identifier),))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(409,'记录已删除，请刷新。')
        return {**result,'trash_kind':kind}

@app.delete('/api/objects/{identifier}')
def delete_object(identifier: UUID):
    return move_to_trash('object',identifier)

@app.delete('/api/canvases/{identifier}')
def delete_canvas(identifier: UUID):
    return move_to_trash('canvas',identifier)

@app.delete('/api/sessions/{identifier}')
def delete_session(identifier: UUID):
    return move_to_trash('session',identifier)

@app.delete('/api/runs/{identifier}')
def delete_run(identifier: UUID):
    return move_to_trash('run',identifier)

@app.delete('/api/attachments/{identifier}')
def delete_attachment(identifier: UUID):
    return move_to_trash('attachment',identifier)

class AttachmentRename(BaseModel):
    original_name: str = Field(min_length=1,max_length=255)

@app.patch('/api/attachments/{identifier}')
def rename_attachment(identifier: UUID,data: AttachmentRename):
    with db() as cursor:
        require(cursor,'attachments',identifier)
        name = Path(data.original_name.strip()).name
        if not name:
            raise HTTPException(422,'附件名称不能为空。')
        cursor.execute('UPDATE attachments SET original_name=%s WHERE id=%s RETURNING *',(name,str(identifier)))
        return cursor.fetchone()

@app.get('/api/trash')
def list_trash():
    rows=[]
    with db() as cursor:
        for kind,table in TRASH_TABLES.items():
            cursor.execute(sql.SQL('SELECT * FROM {} WHERE deleted_at IS NOT NULL').format(sql.Identifier(table)))
            for row in cursor.fetchall():
                title=row.get('title') or row.get('objective') or row.get('original_name') or row.get('hypothesis_md') or ('知识关系' if kind=='relation' else '实验运行')
                rows.append({'kind':kind,'id':row['id'],'title':title,'deleted_at':row['deleted_at']})
    return sorted(rows,key=lambda row:row['deleted_at'],reverse=True)

@app.post('/api/trash/{kind}/{identifier}/restore')
def restore_record(kind: str,identifier: UUID):
    if kind not in TRASH_TABLES:
        raise HTTPException(404,'记录类型不存在。')
    table=TRASH_TABLES[kind]
    with db() as cursor:
        cursor.execute(sql.SQL('SELECT * FROM {} WHERE id=%s AND deleted_at IS NOT NULL FOR UPDATE').format(sql.Identifier(table)),(str(identifier),))
        row=cursor.fetchone()
        if not row:
            raise HTTPException(404,'回收站记录不存在。')
        if kind=='relation':
            for parent in [row['source_id'],row['target_id']]:
                cursor.execute('SELECT deleted_at FROM objects WHERE id=%s',(str(parent),))
                if cursor.fetchone()['deleted_at']:
                    raise HTTPException(409,'请先恢复关系两端的知识对象。')
        if kind=='run':
            cursor.execute('SELECT deleted_at FROM objects WHERE id=%s',(str(row['experiment_id']),))
            if cursor.fetchone()['deleted_at']:
                raise HTTPException(409,'请先恢复所属实验主题。')
        version=',version=version+1' if 'version' in row else ''
        cursor.execute(sql.SQL('UPDATE {} SET deleted_at=NULL' + version + ' WHERE id=%s RETURNING *').format(sql.Identifier(table)),(str(identifier),))
        return cursor.fetchone()

@app.delete('/api/trash/{kind}/{identifier}')
def permanently_delete(kind: str,identifier: UUID):
    if kind not in TRASH_TABLES:
        raise HTTPException(404,'记录类型不存在。')
    files=[]
    with db() as cursor:
        cursor.execute(sql.SQL('SELECT * FROM {} WHERE id=%s AND deleted_at IS NOT NULL FOR UPDATE').format(sql.Identifier(TRASH_TABLES[kind])),(str(identifier),))
        row=cursor.fetchone()
        if not row:
            raise HTTPException(404,'只能永久删除回收站中的记录。')
        if kind=='object':
            # Preserve the layout as text cards, without dangling object IDs.
            cursor.execute('''UPDATE canvases SET version=version+1,updated_at=now()
                WHERE id IN (SELECT canvas_id FROM canvas_items WHERE object_id=%s)''',(str(identifier),))
            cursor.execute('''UPDATE canvas_items SET item_type='text',object_id=NULL,
                properties=properties || jsonb_build_object('text',%s)
                WHERE object_id=%s''',(row['title']+'（原知识对象已永久删除）',str(identifier)))
            cursor.execute('DELETE FROM relations WHERE source_id=%s OR target_id=%s',(str(identifier),str(identifier)))
            cursor.execute('DELETE FROM relation_evidence WHERE evidence_object_id=%s AND source_url IS NULL',(str(identifier),))
            cursor.execute('UPDATE relation_evidence SET evidence_object_id=NULL WHERE evidence_object_id=%s',(str(identifier),))
            cursor.execute('DELETE FROM session_objects WHERE object_id=%s',(str(identifier),))
            cursor.execute('DELETE FROM experiment_runs WHERE experiment_id=%s',(str(identifier),))
            cursor.execute('SELECT attachment_id FROM object_attachments WHERE object_id=%s',(str(identifier),))
            attachment_ids=[item['attachment_id'] for item in cursor.fetchall()]
            cursor.execute('DELETE FROM object_attachments WHERE object_id=%s',(str(identifier),))
            for attachment_id in attachment_ids:
                cursor.execute('''DELETE FROM attachments WHERE id=%s AND NOT EXISTS
                    (SELECT 1 FROM object_attachments WHERE attachment_id=%s) RETURNING relative_path''',(str(attachment_id),str(attachment_id)))
                attachment=cursor.fetchone()
                if attachment:
                    files.append(attachment_path(attachment['relative_path']))
            # Old canvas snapshots must not reintroduce removed references.
            cursor.execute('''DELETE FROM canvas_revisions WHERE snapshot::text LIKE %s''',('%'+str(identifier)+'%',))
        if kind=='relation':
            cursor.execute('''UPDATE canvases SET version=version+1,updated_at=now()
                WHERE id IN (SELECT canvas_id FROM canvas_edges WHERE relation_id=%s)''',(str(identifier),))
            cursor.execute('DELETE FROM canvas_revisions WHERE snapshot::text LIKE %s',('%'+str(identifier)+'%',))
        if kind=='attachment':
            cursor.execute('DELETE FROM object_attachments WHERE attachment_id=%s',(str(identifier),))
            files.append(attachment_path(row['relative_path']))
        cursor.execute(sql.SQL('DELETE FROM {} WHERE id=%s').format(sql.Identifier(TRASH_TABLES[kind])),(str(identifier),))
    warnings=[]
    for path in files:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            warnings.append('记录已删除，但附件文件清理失败，请检查本地附件目录权限。')
    return {'deleted':True,'kind':kind,'id':identifier,'warnings':warnings}

def attachment_path(relative):
    path = (STORAGE / relative).resolve()
    if not path.is_relative_to((STORAGE / 'attachments').resolve()):
        raise HTTPException(422,'附件路径无效。')
    return path

@app.post('/api/objects/{identifier}/attachments',status_code=201)
async def upload_attachment(identifier: UUID,file: UploadFile = File(...)):
    content = await file.read(32 * 1024 * 1024 + 1)
    if len(content) > 32 * 1024 * 1024:
        raise HTTPException(413,'单个资料附件上限为 32 MB；大型数据与权重请记录外部路径。')
    attachment_id = uuid4()
    relative = f'attachments/{attachment_id}'
    path = attachment_path(relative)
    try:
        with db() as cursor:
            require(cursor,'objects',identifier)
            path.write_bytes(content)
            cursor.execute('INSERT INTO attachments(id,original_name,relative_path,mime_type,size_bytes,sha256) VALUES (%s,%s,%s,%s,%s,%s) RETURNING *', (str(attachment_id),Path(file.filename or 'attachment').name,relative,file.content_type or 'application/octet-stream',len(content),hashlib.sha256(content).hexdigest()))
            row = cursor.fetchone()
            cursor.execute('INSERT INTO object_attachments(object_id,attachment_id) VALUES (%s,%s)', (str(identifier),str(attachment_id)))
        return row
    except Exception:
        path.unlink(missing_ok=True)
        raise

@app.get('/api/objects/{identifier}/attachments')
def object_attachments(identifier: UUID):
    with db() as cursor:
        cursor.execute('SELECT a.* FROM attachments a JOIN object_attachments oa ON oa.attachment_id=a.id WHERE oa.object_id=%s AND a.deleted_at IS NULL', (str(identifier),))
        return cursor.fetchall()

@app.get('/api/attachments/{identifier}')
def download_attachment(identifier: UUID):
    with db() as cursor:
        row = require(cursor,'attachments',identifier)
    path = attachment_path(row['relative_path'])
    if not path.is_file():
        raise HTTPException(404,'附件文件未找到。')
    return FileResponse(path,filename=row['original_name'],media_type=row['mime_type'])

def export_material_record(identifier):
    with db() as cursor:
        item=object_with_tags(cursor,require(cursor,'objects',identifier))
        cursor.execute('''SELECT r.*,a.title AS source_title,b.title AS target_title
            FROM relations r JOIN objects a ON a.id=r.source_id JOIN objects b ON b.id=r.target_id
            WHERE r.deleted_at IS NULL AND (r.source_id=%s OR r.target_id=%s) ORDER BY r.created_at''',
            (str(identifier),str(identifier)))
        relations=cursor.fetchall()
        for relation in relations:
            cursor.execute('SELECT * FROM relation_evidence WHERE relation_id=%s ORDER BY id',(relation['id'],))
            relation['evidence']=cursor.fetchall()
        cursor.execute('''SELECT a.original_name,a.mime_type,a.size_bytes FROM attachments a
            JOIN object_attachments oa ON oa.attachment_id=a.id
            WHERE oa.object_id=%s AND a.deleted_at IS NULL ORDER BY a.created_at''',(str(identifier),))
        attachments=cursor.fetchall()
    return {'object':item,'relations':relations,'attachments':attachments}

@app.get('/api/objects/{identifier}/export')
def export_material(identifier: UUID, format: Literal['md','docx','pdf']='md'):
    record=export_material_record(identifier)
    markdown=material_markdown(record)
    title=record['object']['title'].strip() or 'knowledge-material'
    safe=re.sub(r'[\\/:*?"<>|\x00-\x1f]+','-',title).strip(' .')[:80] or 'knowledge-material'
    fallback=f'knowledge-material.{format}'
    headers={'Content-Disposition':f"attachment; filename={fallback}; filename*=UTF-8''{quote(f'{safe}.{format}')}"}
    if format=='md':
        return Response(markdown.encode('utf-8'),media_type='text/markdown; charset=utf-8',headers=headers)
    if format=='docx':
        return Response(material_docx(markdown),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers=headers)
    return Response(material_pdf(markdown),media_type='application/pdf',headers=headers)

TABLES = ['objects','tags','object_tags','relations','relation_evidence','canvases','canvas_items','canvas_edges','learning_sessions','session_objects','experiment_runs','run_artifacts','attachments','object_attachments','object_revisions','canvas_revisions','source_imports']
BACKUP_V1_TABLES = TABLES[:-1]
JSON_FIELDS = {'metadata','viewport','properties','config','environment','metrics','snapshot','extracted_metadata'}

@app.get('/api/export')
def export_backup():
    output = io.BytesIO()
    with db() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        tables = {}
        for table in TABLES:
            cursor.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(table)))
            tables[table] = jsonable_encoder(cursor.fetchall())
        manifest = {'format':'embodied-knowledge','version':2,'created_at':datetime.now().isoformat(),'tables':tables,'external_artifacts_included':False}
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
            for item in tables['attachments']:
                path = attachment_path(item['relative_path'])
                if not path.is_file():
                    raise HTTPException(409,'附件缺失，请修复文件后再备份。')
                archive.write(path,item['relative_path'])
            for item in tables['objects']:
                archive.writestr(f"notes/{item['id']}.md",item['body_md'])
    return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="knowledge-backup.zip"'})

def inspect_backup(content):
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        if sum(item.file_size for item in archive.infolist()) > 256 * 1024 * 1024:
            raise HTTPException(413,'解压后的备份超过 256 MB。')
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise HTTPException(422,'备份包含重复文件名。')
        manifest = json.loads(archive.read('manifest.json'))
        version=manifest.get('version')
        table_names=set(manifest.get('tables',{}))
        if manifest.get('format') != 'embodied-knowledge' or not (
            (version == 1 and table_names == set(BACKUP_V1_TABLES)) or
            (version == 2 and table_names == set(TABLES))
        ):
            raise HTTPException(422,'备份格式或版本不支持。')
        tables = manifest['tables']
        if version == 1:
            tables['source_imports']=[]
        if not all(isinstance(rows,list) and all(isinstance(row,dict) for row in rows) for rows in tables.values()):
            raise HTTPException(422,'备份表结构无效。')
        for item in tables['attachments']:
            attachment_path(item['relative_path'])
            data = archive.read(item['relative_path'])
            if len(data) != item['size_bytes'] or (item['sha256'] and hashlib.sha256(data).hexdigest() != item['sha256']):
                raise HTTPException(422,'附件校验失败。')
        return archive,tables
    except HTTPException:
        raise
    except (ValueError,KeyError,TypeError,zipfile.BadZipFile):
        raise HTTPException(422,'备份损坏或缺少必要内容。')

@app.post('/api/import')
async def import_backup(file: UploadFile = File(...),dry_run: bool = True):
    content = await file.read(128 * 1024 * 1024 + 1)
    if len(content) > 128 * 1024 * 1024:
        raise HTTPException(413,'备份文件超过 128 MB。')
    archive,tables = inspect_backup(content)
    created_files = []
    try:
        with db() as cursor:
            conflicts = {}
            for table in TABLES:
                ids = [row['id'] for row in tables[table] if 'id' in row]
                if ids:
                    cursor.execute(sql.SQL('SELECT id FROM {} WHERE id = ANY(%s::uuid[])').format(sql.Identifier(table)),(ids,))
                    rows = cursor.fetchall()
                    if rows:
                        conflicts[table] = len(rows)
            summary = {'counts':{table:len(rows) for table,rows in tables.items()},'conflicts':conflicts,'external_artifacts_included':False}
            if dry_run:
                return summary
            if conflicts:
                raise HTTPException(409,'记录 ID 冲突；请恢复到空数据库，或使用不冲突的备份。现有数据未覆盖。')
            cursor.execute('SET CONSTRAINTS ALL DEFERRED')
            for table in TABLES:
                cursor.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s',(SCHEMA,table))
                allowed = {row['column_name'] for row in cursor.fetchall()}
                for row in tables[table]:
                    if not set(row).issubset(allowed):
                        raise HTTPException(422,'备份包含未知字段。')
                    columns = list(row)
                    values = [json_value(row[key]) if key in JSON_FIELDS else row[key] for key in columns]
                    statement = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns))
                    cursor.execute(statement,values)
            for item in tables['attachments']:
                path = attachment_path(item['relative_path'])
                if path.exists():
                    raise HTTPException(409,'附件路径冲突，恢复已取消。')
                path.parent.mkdir(parents=True,exist_ok=True)
                created_files.append(path)
                path.write_bytes(archive.read(item['relative_path']))
        return {**summary,'restored':True}
    except Exception:
        for path in created_files:
            path.unlink(missing_ok=True)
        raise
    finally:
        archive.close()
