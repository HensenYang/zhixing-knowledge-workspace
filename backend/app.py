"""Local personal knowledge workspace. PostgreSQL is the source of truth."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import shutil
import zipfile

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, Response, JSONResponse
from pydantic import BaseModel, Field
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor
from backend.llm import router as llm_router

from .exporters import material_docx, material_markdown, material_pdf
from .importers import import_locator, import_pdf
from . import zotero
from . import import_assets
from . import import_analysis

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(Path(os.environ.get('WORKSPACE_ENV_FILE', str(ROOT / '.env'))))
STORAGE = Path(os.environ.get('STORAGE_ROOT', 'storage'))
if not STORAGE.is_absolute():
    STORAGE = ROOT / STORAGE
STORAGE.mkdir(parents=True, exist_ok=True)
(STORAGE / 'attachments').mkdir(exist_ok=True)
SCHEMA = os.environ.get('KNOWLEDGE_SCHEMA', 'knowledge')
app = FastAPI(title='Embodied Knowledge Workspace', version='0.1.0')
app.include_router(llm_router)
logger = logging.getLogger('knowledge-workspace')
SESSION_COOKIE = 'knowledge_session'
SESSION_DAYS = 30
current_user_id = ContextVar('current_user_id', default=None)
current_workspace_id = ContextVar('current_workspace_id', default=None)
current_workspace_role = ContextVar('current_workspace_role', default=None)

Kind = Literal['concept','resource','repository','model','dataset','benchmark','experiment','question','task']
RelationType = Literal['depends_on','implements','uses','evaluates','supports','questions','compares_with','related_to']
TRASH_TABLES = {'object':'objects','relation':'relations','canvas':'canvases',
                'session':'learning_sessions','run':'experiment_runs','attachment':'attachments',
                'path':'learning_paths'}

@contextmanager
def raw_db():
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise HTTPException(503, '数据库尚未配置，请运行数据库初始化脚本。')
    connection = None
    try:
        connection = psycopg2.connect(dsn, connect_timeout=5)
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql.SQL('SET LOCAL search_path TO {}, public').format(sql.Identifier(SCHEMA)))
                yield cursor
    finally:
        if connection is not None:
            connection.close()

@contextmanager
def db(isolation=None):
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise HTTPException(503, '数据库尚未配置，请在本机运行 scripts/setup_database.ps1。')
    connection = None
    try:
        connection = psycopg2.connect(dsn, connect_timeout=5)
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                if isolation:
                    cursor.execute(sql.SQL('SET TRANSACTION ISOLATION LEVEL {}').format(sql.SQL(isolation)))
                cursor.execute(sql.SQL('SET LOCAL search_path TO {}, public').format(sql.Identifier(SCHEMA)))
                workspace_id = current_workspace_id.get()
                user_id = current_user_id.get()
                if workspace_id:
                    cursor.execute("SELECT set_config('app.workspace_id',%s,true)",(str(workspace_id),))
                if user_id:
                    cursor.execute("SELECT set_config('app.user_id',%s,true)",(str(user_id),))
                yield cursor
    except psycopg2.IntegrityError:
        raise HTTPException(409, '存在重复记录或无效引用，修改未保存。')
    except psycopg2.OperationalError:
        raise HTTPException(503, '无法连接 PostgreSQL，请检查本地服务与 .env 配置。')
    except psycopg2.ProgrammingError as error:
        logger.exception('Database programming error')
        raise HTTPException(503, '数据库结构未就绪，请运行 scripts/migrate.py。')
    finally:
        if connection is not None:
            connection.close()

def require(cursor, table, identifier):
    active = sql.SQL(' AND deleted_at IS NULL') if table in TRASH_TABLES.values() else sql.SQL('')
    workspace = sql.SQL(' AND workspace_id=%s') if table == 'learning_paths' else sql.SQL('')
    parameters = (str(identifier),current_workspace_id.get()) if table == 'learning_paths' else (str(identifier),)
    cursor.execute(sql.SQL('SELECT * FROM {} WHERE id=%s{}{}').format(
        sql.Identifier(table),active,workspace),parameters)
    row = cursor.fetchone()
    if not row:
        raise HTTPException(404, '记录不存在。')
    return row

def json_value(value):
    return Json(jsonable_encoder(value))

def password_hash(password):
    if len(password) < 8:
        raise HTTPException(422,'密码至少需要 8 个字符。')
    salt = secrets.token_bytes(16)
    rounds = 310000
    digest = hashlib.pbkdf2_hmac('sha256',password.encode(),salt,rounds)
    return f'pbkdf2_sha256${rounds}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}'

def password_matches(password, encoded):
    try:
        _, rounds, salt, expected = encoded.split('$',3)
        digest = hashlib.pbkdf2_hmac('sha256',password.encode(),base64.b64decode(salt),int(rounds))
        return hmac.compare_digest(base64.b64encode(digest).decode(),expected)
    except (ValueError,TypeError):
        return False

def session_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def require_roles(*roles):
    if current_workspace_role.get() not in roles:
        raise HTTPException(403,'当前角色没有执行此操作的权限。')

def user_payload(cursor,user):
    cursor.execute('''SELECT w.id,w.name,wm.role FROM workspaces w JOIN workspace_members wm ON wm.workspace_id=w.id
        WHERE wm.user_id=%s ORDER BY wm.joined_at,w.name''',(user['id'],))
    return {'id':user['id'],'email':user['email'],'display_name':user['display_name'],'workspaces':cursor.fetchall()}

@app.middleware('http')
async def collaboration_context(request: Request, call_next):
    path = request.url.path
    public = (
        path in {'/api/health','/api/auth/register','/api/auth/login'}
        or path.startswith('/api/shared/learning-paths/')
        or not path.startswith('/api/')
    )
    if public:
        return await call_next(request)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return JSONResponse({'detail':'请先登录。'},status_code=401)
    try:
        with raw_db() as cursor:
            cursor.execute('''SELECT u.* FROM auth_sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=%s AND s.expires_at>now()''',(session_hash(token),))
            user = cursor.fetchone()
            if not user:
                return JSONResponse({'detail':'登录已过期，请重新登录。'},status_code=401)
            requested = request.headers.get('X-Workspace-ID')
            cursor.execute('''SELECT wm.workspace_id,wm.role FROM workspace_members wm
                WHERE wm.user_id=%s AND (%s IS NULL OR wm.workspace_id=%s::uuid)
                ORDER BY wm.joined_at LIMIT 1''',(user['id'],requested,requested))
            membership = cursor.fetchone()
            if not membership:
                return JSONResponse({'detail':'工作区不存在或你不是成员。'},status_code=403)
    except (psycopg2.Error,HTTPException):
        return JSONResponse({'detail':'协作数据库尚未就绪，请运行最新迁移。'},status_code=503)
    user_token = current_user_id.set(user['id'])
    workspace_token = current_workspace_id.set(membership['workspace_id'])
    role_token = current_workspace_role.set(membership['role'])
    try:
        if request.method not in {'GET','HEAD','OPTIONS'}:
            collaboration_paths = ('/api/comments','/api/reviews','/api/auth/','/api/workspaces')
            if not path.startswith(collaboration_paths) and membership['role'] not in {'owner','editor'}:
                return JSONResponse({'detail':'当前角色只有查看、评论或审核权限。'},status_code=403)
        response = await call_next(request)
        response.headers['X-Workspace-ID'] = str(membership['workspace_id'])
        if request.method not in {'GET','HEAD','OPTIONS'} and response.status_code < 400 and not path.startswith('/api/auth/'):
            try:
                pieces = path.strip('/').split('/')
                target_id = pieces[2] if len(pieces)>2 else None
                UUID(target_id) if target_id else None
                with db() as cursor:
                    cursor.execute('INSERT INTO activity_events(workspace_id,actor_id,action,target_id,metadata) VALUES (%s,%s,%s,%s,%s)',
                                   (membership['workspace_id'],user['id'],f'{request.method} {path}',target_id,json_value({})))
            except (ValueError,psycopg2.Error):
                pass
        return response
    finally:
        current_user_id.reset(user_token)
        current_workspace_id.reset(workspace_token)
        current_workspace_role.reset(role_token)

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
    preview_token: str | None = Field(default=None,pattern=r'^[A-Za-z0-9_-]{32}$')
    save_as_note: bool = False

class ZoteroSearchInput(BaseModel):
    query: str = Field(min_length=1,max_length=1000)
    qmode: Literal['titleCreatorYear','everything'] = 'titleCreatorYear'
    tag: str = Field(default='',max_length=200)
    limit: int = Field(default=20,ge=1,le=100)

class ZoteroPreviewInput(BaseModel):
    item_key: str = Field(pattern=r'^[A-Z0-9]{8}$')
    include_fulltext: bool = True
    include_media: bool = True

class LearningPathStepInput(BaseModel):
    id: UUID | None = None
    object_id: UUID | None = None
    title: str = Field(min_length=1,max_length=500)
    guidance_md: str = ''
    completion_criteria_md: str = ''
    estimated_minutes: int | None = Field(default=None,ge=0,le=100000)

class LearningPathInput(BaseModel):
    title: str = Field(min_length=1,max_length=500)
    objective_md: str = ''
    description_md: str = ''
    completion_criteria_md: str = ''
    steps: list[LearningPathStepInput] = Field(default_factory=list,max_length=100)
    version: int | None = Field(default=None,ge=1)

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
        cursor.execute('''SELECT o.id,o.title,o.deleted_at FROM source_imports s JOIN objects o ON o.id=s.object_id
            WHERE s.source_type=%s AND s.source_key=%s''', (preview['source_type'],preview['source_key']))
        preview['existing_import'] = cursor.fetchone()
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
        'zotero': zotero.status(),
        'mcp': {
            'enabled': bool(os.environ.get('MCP_IMPORT_SERVER_URL','').strip()),
            'tool': os.environ.get('MCP_IMPORT_TOOL','import_source'),
        },
    }

@app.post('/api/source-imports/zotero/search')
async def search_zotero(data: ZoteroSearchInput):
    return await zotero.search(data.query,data.qmode,data.tag,data.limit)

@app.post('/api/source-imports/zotero/preview')
async def preview_zotero(data: ZoteroPreviewInput):
    preview = await zotero.preview(data.item_key,data.include_fulltext)
    if data.include_media:
        preview = await import_assets.zotero_pdf(preview,data.item_key,STORAGE)
    return add_duplicate_hints(preview)

@app.post('/api/source-imports/preview')
async def preview_source(data: SourcePreviewInput):
    return add_duplicate_hints(await import_locator(data.source,data.source_type))

@app.post('/api/source-imports/analyze')
async def analyze_source(data: import_analysis.AnalysisInput):
    return await import_analysis.analyze(data)

@app.post('/api/source-imports/preview-file')
async def preview_source_file(file: UploadFile = File(...)):
    content = await file.read(32 * 1024 * 1024 + 1)
    return add_duplicate_hints(import_assets.local_pdf(content,Path(file.filename or 'document.pdf').name,STORAGE))

@app.get('/api/source-imports/assets/{token}/{asset_id}')
def preview_import_asset(token: str,asset_id: UUID):
    path,asset = import_assets.asset_file(STORAGE,token,str(asset_id))
    return FileResponse(path,media_type=asset['mime_type'],filename=asset['filename'],
                        content_disposition_type='inline',headers={'X-Content-Type-Options':'nosniff'})

@app.post('/api/source-imports/commit',status_code=201)
def commit_source_import(data: SourceImportCommit):
    validate_object(data.object)
    written=[]
    try:
        with import_assets.claim(STORAGE,data.preview_token,data.source_type,data.source_key) as manifest:
            with db() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                    (json.dumps([data.source_type,data.source_key]),))
                cursor.execute('''SELECT s.object_id,o.title,o.deleted_at FROM source_imports s
                    JOIN objects o ON o.id=s.object_id WHERE s.source_type=%s AND s.source_key=%s''',
                    (data.source_type,data.source_key))
                existing=cursor.fetchone()
                if existing and existing['deleted_at'] is None and not data.save_as_note:
                    raise HTTPException(409,{'message':'该来源已经导入，请打开已有资料或选择另存笔记。',
                        'existing_import':{'id':str(existing['object_id']),'title':existing['title'],'deleted_at':None}})
                item=data.object
                if data.save_as_note:
                    item.metadata={**item.metadata,'derived_source':{'source_type':data.source_type,
                        'source_key':data.source_key,'object_id':str(existing['object_id']) if existing else None}}
                item.body_md=import_assets.resolve_body(item.body_md,manifest)
                assets=import_assets.persist(STORAGE,data.preview_token,manifest,written)
                if assets:
                    item.metadata={**item.metadata,'imported_assets':[{key:asset[key] for key in ('id','filename','kind','page')} for asset in assets]}
                cursor.execute('''INSERT INTO objects(kind,title,summary,body_md,source_url,reading_status,mastery_status,metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (item.kind,item.title.strip(),item.summary,item.body_md,item.source_url,item.reading_status,item.mastery_status,json_value(item.metadata)))
                row=cursor.fetchone()
                set_tags(cursor,row['id'],item.tags)
                if not data.save_as_note:
                    cursor.execute('''INSERT INTO source_imports(source_type,source_key,source_url,original_name,extracted_metadata,object_id)
                        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(source_type,source_key) DO UPDATE SET
                        source_url=EXCLUDED.source_url,original_name=EXCLUDED.original_name,
                        extracted_metadata=EXCLUDED.extracted_metadata,object_id=EXCLUDED.object_id''',
                        (data.source_type,data.source_key,item.source_url,data.extracted_metadata.get('file_name'),json_value(data.extracted_metadata),row['id']))
                for asset in assets:
                    cursor.execute('INSERT INTO attachments(id,original_name,relative_path,mime_type,size_bytes,sha256) VALUES (%s,%s,%s,%s,%s,%s)',
                        (asset['id'],asset['filename'],f"attachments/{asset['id']}",asset['mime_type'],asset['size_bytes'],asset['sha256']))
                    cursor.execute('INSERT INTO object_attachments(object_id,attachment_id) VALUES (%s,%s)',(row['id'],asset['id']))
                result=object_with_tags(cursor,row)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    if data.preview_token:
        import_assets.discard(STORAGE,data.preview_token)
    return result


def learning_path_document(cursor, identifier=None, share_token=None):
    if share_token is not None:
        cursor.execute('''SELECT * FROM learning_paths WHERE share_token=%s AND status='published'
            AND deleted_at IS NULL''',(share_token,))
    else:
        cursor.execute('''SELECT * FROM learning_paths WHERE id=%s AND workspace_id=%s
            AND deleted_at IS NULL''',(str(identifier),current_workspace_id.get()))
    path=cursor.fetchone()
    if not path:
        raise HTTPException(404,'学习路径不存在或分享已经停止。')
    if share_token is not None:
        cursor.execute("SELECT set_config('app.workspace_id',%s,true)",(str(path['workspace_id']),))
    cursor.execute('''SELECT s.*,o.title AS object_title,o.summary AS object_summary,
        o.kind AS object_kind,o.deleted_at AS object_deleted_at
        FROM learning_path_steps s LEFT JOIN objects o ON o.id=s.object_id
        WHERE s.path_id=%s ORDER BY s.position''',(path['id'],))
    steps=cursor.fetchall()
    for step in steps:
        object_deleted_at=step.pop('object_deleted_at')
        step['object_available']=step['object_id'] is not None and object_deleted_at is None
    return {**path,'steps':steps}

def replace_learning_path_steps(cursor, path_id, steps):
    step_ids=[step.id or uuid4() for step in steps]
    if len(step_ids) != len(set(step_ids)):
        raise HTTPException(422,'学习步骤 ID 不能重复。')
    for step in steps:
        if not step.title.strip():
            raise HTTPException(422,'学习步骤标题不能为空。')
        if step.object_id is not None:
            require(cursor,'objects',step.object_id)
    cursor.execute('DELETE FROM learning_path_steps WHERE path_id=%s',(str(path_id),))
    for position,(step,step_id) in enumerate(zip(steps,step_ids)):
        cursor.execute('''INSERT INTO learning_path_steps
            (id,path_id,object_id,position,title,guidance_md,completion_criteria_md,estimated_minutes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            (str(step_id),str(path_id),str(step.object_id) if step.object_id else None,position,
             step.title.strip(),step.guidance_md,step.completion_criteria_md,step.estimated_minutes))

@app.get('/api/learning-paths')
def list_learning_paths():
    with db() as cursor:
        cursor.execute('''SELECT p.*,count(s.id)::integer AS step_count,
            COALESCE(sum(s.estimated_minutes),0)::integer AS estimated_minutes
            FROM learning_paths p LEFT JOIN learning_path_steps s ON s.path_id=p.id
            WHERE p.workspace_id=%s AND p.deleted_at IS NULL
            GROUP BY p.id ORDER BY p.updated_at DESC''',(current_workspace_id.get(),))
        return cursor.fetchall()

@app.post('/api/learning-paths',status_code=201)
def create_learning_path(data: LearningPathInput):
    if not data.title.strip():
        raise HTTPException(422,'学习路径标题不能为空。')
    with db() as cursor:
        cursor.execute('''INSERT INTO learning_paths
            (workspace_id,title,objective_md,description_md,completion_criteria_md)
            VALUES (%s,%s,%s,%s,%s) RETURNING *''',
            (current_workspace_id.get(),data.title.strip(),data.objective_md,
             data.description_md,data.completion_criteria_md))
        path=cursor.fetchone()
        replace_learning_path_steps(cursor,path['id'],data.steps)
        return learning_path_document(cursor,path['id'])

@app.get('/api/shared/learning-paths/{share_token}')
def shared_learning_path(share_token: str):
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',share_token):
        raise HTTPException(404,'学习路径不存在或分享已经停止。')
    with raw_db() as cursor:
        return learning_path_document(cursor,share_token=share_token)

@app.get('/api/learning-paths/{identifier}')
def get_learning_path(identifier: UUID):
    with db() as cursor:
        return learning_path_document(cursor,identifier)

@app.put('/api/learning-paths/{identifier}')
def update_learning_path(identifier: UUID,data: LearningPathInput):
    if not data.title.strip():
        raise HTTPException(422,'学习路径标题不能为空。')
    if data.version is None:
        raise HTTPException(422,'保存学习路径需要当前版本号。')
    with db() as cursor:
        cursor.execute('''SELECT * FROM learning_paths WHERE id=%s AND workspace_id=%s
            AND deleted_at IS NULL FOR UPDATE''',(str(identifier),current_workspace_id.get()))
        path=cursor.fetchone()
        if not path:
            raise HTTPException(404,'学习路径不存在。')
        if path['version'] != data.version:
            raise HTTPException(409,'另一标签页已经修改这条学习路径，请刷新后合并。')
        cursor.execute('''UPDATE learning_paths SET title=%s,objective_md=%s,description_md=%s,
            completion_criteria_md=%s,version=version+1,updated_at=now()
            WHERE id=%s RETURNING *''',
            (data.title.strip(),data.objective_md,data.description_md,data.completion_criteria_md,str(identifier)))
        replace_learning_path_steps(cursor,identifier,data.steps)
        return learning_path_document(cursor,identifier)

@app.post('/api/learning-paths/{identifier}/publish')
def publish_learning_path(identifier: UUID):
    with db() as cursor:
        path=learning_path_document(cursor,identifier)
        if not path['objective_md'].strip():
            raise HTTPException(422,'发布前请填写学习目标。')
        if not path['completion_criteria_md'].strip():
            raise HTTPException(422,'发布前请填写整条路径的完成条件。')
        if not path['steps']:
            raise HTTPException(422,'发布前请至少添加一个学习步骤。')
        if any(not step['completion_criteria_md'].strip() for step in path['steps']):
            raise HTTPException(422,'发布前请为每个学习步骤填写完成条件。')
        token=path['share_token'] or secrets.token_urlsafe(18)
        cursor.execute('''UPDATE learning_paths SET status='published',share_token=%s,
            version=version+1,updated_at=now() WHERE id=%s RETURNING *''',(token,str(identifier)))
        return learning_path_document(cursor,identifier)

@app.post('/api/learning-paths/{identifier}/unpublish')
def unpublish_learning_path(identifier: UUID):
    with db() as cursor:
        learning_path_document(cursor,identifier)
        cursor.execute('''UPDATE learning_paths SET status='draft',share_token=NULL,
            version=version+1,updated_at=now() WHERE id=%s AND deleted_at IS NULL RETURNING *''',(str(identifier),))
        return learning_path_document(cursor,identifier)

@app.delete('/api/learning-paths/{identifier}')
def delete_learning_path(identifier: UUID):
    with db() as cursor:
        learning_path_document(cursor,identifier)
        cursor.execute('''UPDATE learning_paths SET status='draft',share_token=NULL,deleted_at=now(),
            version=version+1,updated_at=now() WHERE id=%s AND deleted_at IS NULL RETURNING *''',(str(identifier),))
        row=cursor.fetchone()
        if not row:
            raise HTTPException(409,'学习路径已删除，请刷新。')
        return {**row,'trash_kind':'path'}

class AuthInput(BaseModel):
    email: str = Field(min_length=3,max_length=320)
    password: str = Field(min_length=8,max_length=256)
    display_name: str = Field(default='',max_length=100)

def set_login_cookie(response,token):
    response.set_cookie(SESSION_COOKIE,token,max_age=SESSION_DAYS*86400,httponly=True,
                        secure=os.environ.get('COOKIE_SECURE','false').lower()=='true',
                        samesite='lax',path='/')

def create_login(cursor,user_id):
    token=secrets.token_urlsafe(32)
    cursor.execute("INSERT INTO auth_sessions(user_id,token_hash,expires_at) VALUES (%s,%s,now()+interval '30 days')",
                   (user_id,session_hash(token)))
    return token

@app.post('/api/auth/register',status_code=201)
def register(data: AuthInput,response: Response):
    email=data.email.strip().lower()
    if '@' not in email or not data.display_name.strip():
        raise HTTPException(422,'请填写有效邮箱和显示名称。')
    with raw_db() as cursor:
        cursor.execute('SELECT 1 FROM users WHERE email=%s',(email,))
        if cursor.fetchone():
            raise HTTPException(409,'该邮箱已经注册。')
        cursor.execute('SELECT count(*) AS count FROM users')
        first=cursor.fetchone()['count']==0
        cursor.execute('INSERT INTO users(email,display_name,password_hash) VALUES (%s,%s,%s) RETURNING *',
                       (email,data.display_name.strip(),password_hash(data.password)))
        user=cursor.fetchone()
        if first:
            cursor.execute('SELECT id FROM workspaces ORDER BY created_at LIMIT 1')
            workspace=cursor.fetchone()
            if workspace:
                cursor.execute('UPDATE workspaces SET created_by=%s,name=%s WHERE id=%s',
                               (user['id'],f"{data.display_name.strip()}的知识空间",workspace['id']))
                workspace_id=workspace['id']
            else:
                cursor.execute('INSERT INTO workspaces(name,created_by) VALUES (%s,%s) RETURNING id',
                               (f"{data.display_name.strip()}的知识空间",user['id']))
                workspace_id=cursor.fetchone()['id']
        else:
            cursor.execute('INSERT INTO workspaces(name,created_by) VALUES (%s,%s) RETURNING id',
                           (f"{data.display_name.strip()}的知识空间",user['id']))
            workspace_id=cursor.fetchone()['id']
        cursor.execute("INSERT INTO workspace_members(workspace_id,user_id,role) VALUES (%s,%s,'owner')",(workspace_id,user['id']))
        token=create_login(cursor,user['id'])
        payload=user_payload(cursor,user)
    set_login_cookie(response,token)
    return payload

@app.post('/api/auth/login')
def login(data: AuthInput,response: Response):
    with raw_db() as cursor:
        cursor.execute('SELECT * FROM users WHERE email=%s',(data.email.strip().lower(),))
        user=cursor.fetchone()
        if not user or not password_matches(data.password,user['password_hash']):
            raise HTTPException(401,'邮箱或密码错误。')
        cursor.execute('DELETE FROM auth_sessions WHERE expires_at<=now()')
        token=create_login(cursor,user['id'])
        payload=user_payload(cursor,user)
    set_login_cookie(response,token)
    return payload

@app.post('/api/auth/logout')
def logout(request: Request,response: Response):
    token=request.cookies.get(SESSION_COOKIE)
    if token:
        with raw_db() as cursor:
            cursor.execute('DELETE FROM auth_sessions WHERE token_hash=%s',(session_hash(token),))
    response.delete_cookie(SESSION_COOKIE,path='/')
    return {'ok':True}

@app.get('/api/auth/me')
def me():
    with raw_db() as cursor:
        cursor.execute('SELECT * FROM users WHERE id=%s',(current_user_id.get(),))
        return user_payload(cursor,cursor.fetchone())

class WorkspaceInput(BaseModel):
    name: str = Field(min_length=1,max_length=120)

class MemberInput(BaseModel):
    email: str = Field(min_length=3,max_length=320)
    role: Literal['owner','editor','reviewer','viewer'] = 'viewer'

class MemberRole(BaseModel):
    role: Literal['owner','editor','reviewer','viewer']

@app.get('/api/workspaces')
def list_workspaces():
    with raw_db() as cursor:
        cursor.execute('''SELECT w.id,w.name,wm.role,w.created_at FROM workspaces w JOIN workspace_members wm ON wm.workspace_id=w.id
            WHERE wm.user_id=%s ORDER BY wm.joined_at,w.name''',(current_user_id.get(),))
        return cursor.fetchall()

@app.post('/api/workspaces',status_code=201)
def create_workspace(data: WorkspaceInput):
    with raw_db() as cursor:
        cursor.execute('INSERT INTO workspaces(name,created_by) VALUES (%s,%s) RETURNING *',(data.name.strip(),current_user_id.get()))
        workspace=cursor.fetchone()
        cursor.execute("INSERT INTO workspace_members(workspace_id,user_id,role) VALUES (%s,%s,'owner')",(workspace['id'],current_user_id.get()))
        return {**workspace,'role':'owner'}

@app.get('/api/workspaces/{identifier}/members')
def list_members(identifier: UUID):
    if str(identifier) != str(current_workspace_id.get()):
        raise HTTPException(403,'请先切换到该工作区。')
    with raw_db() as cursor:
        cursor.execute('''SELECT u.id,u.email,u.display_name,wm.role,wm.joined_at FROM workspace_members wm
            JOIN users u ON u.id=wm.user_id WHERE wm.workspace_id=%s ORDER BY wm.joined_at''',(str(identifier),))
        return cursor.fetchall()

@app.post('/api/workspaces/{identifier}/members',status_code=201)
def add_member(identifier: UUID,data: MemberInput):
    require_roles('owner')
    if str(identifier) != str(current_workspace_id.get()):
        raise HTTPException(403,'请先切换到该工作区。')
    with raw_db() as cursor:
        cursor.execute('SELECT * FROM users WHERE email=%s',(data.email.strip().lower(),))
        user=cursor.fetchone()
        if not user:
            raise HTTPException(404,'该用户尚未注册，请让对方先创建账号。')
        cursor.execute('''INSERT INTO workspace_members(workspace_id,user_id,role) VALUES (%s,%s,%s)
            ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=EXCLUDED.role RETURNING role''',(str(identifier),user['id'],data.role))
        return {'id':user['id'],'email':user['email'],'display_name':user['display_name'],'role':cursor.fetchone()['role']}

@app.patch('/api/workspaces/{identifier}/members/{user_id}')
def change_member_role(identifier: UUID,user_id: UUID,data: MemberRole):
    require_roles('owner')
    if str(identifier) != str(current_workspace_id.get()) or str(user_id) == str(current_user_id.get()):
        raise HTTPException(422,'不能在这里修改自己的所有者角色。')
    with raw_db() as cursor:
        cursor.execute('UPDATE workspace_members SET role=%s WHERE workspace_id=%s AND user_id=%s RETURNING role',(data.role,str(identifier),str(user_id)))
        if not cursor.fetchone():
            raise HTTPException(404,'成员不存在。')
    return {'ok':True}

TARGET_TABLES={'object':'objects','relation':'relations','canvas':'canvases','session':'learning_sessions','run':'experiment_runs'}

def require_target(cursor,target_type,target_id):
    table=TARGET_TABLES.get(target_type)
    if not table:
        raise HTTPException(422,'不支持的协作目标。')
    return require(cursor,table,target_id)

class CommentInput(BaseModel):
    target_type: Literal['object','relation','canvas','session','run']
    target_id: UUID
    body: str = Field(min_length=1,max_length=5000)
    parent_id: UUID | None = None

@app.get('/api/comments')
def list_comments(target_type: str,target_id: UUID):
    with db() as cursor:
        require_target(cursor,target_type,target_id)
        cursor.execute('''SELECT c.*,u.display_name,u.email,ru.display_name AS resolved_by_name FROM comments c
            JOIN users u ON u.id=c.author_id LEFT JOIN users ru ON ru.id=c.resolved_by
            WHERE c.target_type=%s AND c.target_id=%s ORDER BY c.created_at''',(target_type,str(target_id)))
        return cursor.fetchall()

@app.post('/api/comments',status_code=201)
def create_comment(data: CommentInput):
    with db() as cursor:
        require_target(cursor,data.target_type,data.target_id)
        if data.parent_id:
            cursor.execute('SELECT id FROM comments WHERE id=%s AND target_type=%s AND target_id=%s',(str(data.parent_id),data.target_type,str(data.target_id)))
            if not cursor.fetchone():
                raise HTTPException(422,'回复的评论不存在。')
        cursor.execute('''INSERT INTO comments(workspace_id,target_type,target_id,author_id,parent_id,body)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''',(current_workspace_id.get(),data.target_type,str(data.target_id),current_user_id.get(),str(data.parent_id) if data.parent_id else None,data.body.strip()))
        return cursor.fetchone()

@app.post('/api/comments/{identifier}/resolve')
def resolve_comment(identifier: UUID):
    with db() as cursor:
        cursor.execute('''UPDATE comments SET resolved_at=CASE WHEN resolved_at IS NULL THEN now() ELSE NULL END,
            resolved_by=CASE WHEN resolved_at IS NULL THEN %s ELSE NULL END,updated_at=now() WHERE id=%s RETURNING *''',(current_user_id.get(),str(identifier)))
        row=cursor.fetchone()
        if not row:
            raise HTTPException(404,'评论不存在。')
        return row

class ReviewInput(BaseModel):
    target_type: Literal['object','relation','canvas','session','run']
    target_id: UUID
    target_version: int = Field(ge=1)
    note: str = Field(default='',max_length=5000)

class ReviewDecision(BaseModel):
    status: Literal['approved','changes_requested']
    note: str = Field(default='',max_length=5000)

@app.get('/api/reviews')
def list_reviews(target_type: str,target_id: UUID):
    with db() as cursor:
        require_target(cursor,target_type,target_id)
        cursor.execute('''SELECT r.*,a.display_name AS requested_by_name,b.display_name AS reviewed_by_name
            FROM review_requests r JOIN users a ON a.id=r.requested_by LEFT JOIN users b ON b.id=r.reviewed_by
            WHERE r.target_type=%s AND r.target_id=%s ORDER BY r.created_at DESC''',(target_type,str(target_id)))
        return cursor.fetchall()

@app.post('/api/reviews',status_code=201)
def request_review(data: ReviewInput):
    require_roles('owner','editor')
    with db() as cursor:
        target=require_target(cursor,data.target_type,data.target_id)
        if target.get('version',1) != data.target_version:
            raise HTTPException(409,'目标已有新版本，请刷新后重新提交审核。')
        cursor.execute('''INSERT INTO review_requests(workspace_id,target_type,target_id,target_version,requested_by,note)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''',(current_workspace_id.get(),data.target_type,str(data.target_id),data.target_version,current_user_id.get(),data.note))
        return cursor.fetchone()

@app.patch('/api/reviews/{identifier}')
def decide_review(identifier: UUID,data: ReviewDecision):
    require_roles('owner','reviewer')
    with db() as cursor:
        cursor.execute('''UPDATE review_requests SET status=%s,note=%s,reviewed_by=%s,reviewed_at=now()
            WHERE id=%s AND status='pending' RETURNING *''',(data.status,data.note,current_user_id.get(),str(identifier)))
        row=cursor.fetchone()
        if not row:
            raise HTTPException(404,'待审核记录不存在。')
        return row

@app.get('/api/activity')
def activity(limit: int=50,before: int | None=None):
    with db() as cursor:
        cursor.execute('''SELECT e.*,u.display_name FROM activity_events e LEFT JOIN users u ON u.id=e.actor_id
            WHERE (%s IS NULL OR e.id<%s) ORDER BY e.id DESC LIMIT %s''',(before,before,min(max(limit,1),200)))
        return cursor.fetchall()

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
        require(cursor,'objects',identifier)
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
        require(cursor,'canvases',identifier)
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
            workspace = sql.SQL(' AND workspace_id=%s') if kind == 'path' else sql.SQL('')
            parameters = (current_workspace_id.get(),) if kind == 'path' else ()
            cursor.execute(sql.SQL('SELECT * FROM {} WHERE deleted_at IS NOT NULL{}').format(
                sql.Identifier(table),workspace),parameters)
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
        workspace = sql.SQL(' AND workspace_id=%s') if kind == 'path' else sql.SQL('')
        parameters = (str(identifier),current_workspace_id.get()) if kind == 'path' else (str(identifier),)
        cursor.execute(sql.SQL('SELECT * FROM {} WHERE id=%s AND deleted_at IS NOT NULL{} FOR UPDATE').format(
            sql.Identifier(table),workspace),parameters)
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
        workspace = sql.SQL(' AND workspace_id=%s') if kind == 'path' else sql.SQL('')
        parameters = (str(identifier),current_workspace_id.get()) if kind == 'path' else (str(identifier),)
        cursor.execute(sql.SQL('SELECT * FROM {} WHERE id=%s AND deleted_at IS NOT NULL{} FOR UPDATE').format(
            sql.Identifier(TRASH_TABLES[kind]),workspace),parameters)
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
        require(cursor,'objects',identifier)
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

@app.get('/api/attachments/{identifier}/content')
def inline_attachment(identifier: UUID):
    with db() as cursor:
        row = require(cursor,'attachments',identifier)
    path=attachment_path(row['relative_path'])
    if not path.is_file():
        raise HTTPException(404,'附件文件未找到。')
    inline=row['mime_type'] in ('image/png','image/jpeg','image/gif','image/webp','application/pdf')
    return FileResponse(path,filename=row['original_name'],media_type=row['mime_type'],
        content_disposition_type='inline' if inline else 'attachment',headers={'X-Content-Type-Options':'nosniff'})


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

TABLES = ['objects','tags','object_tags','relations','relation_evidence','canvases','canvas_items','canvas_edges','learning_sessions','session_objects','experiment_runs','run_artifacts','attachments','object_attachments','object_revisions','canvas_revisions','source_imports','learning_paths','learning_path_steps']
BACKUP_V1_TABLES = TABLES[:-3]
BACKUP_V2_TABLES = TABLES[:-2]
JSON_FIELDS = {'metadata','viewport','properties','config','environment','metrics','snapshot','extracted_metadata'}
EXPORT_QUERIES = {
    'tags':'SELECT DISTINCT t.* FROM tags t JOIN object_tags ot ON ot.tag_id=t.id JOIN objects o ON o.id=ot.object_id',
    'object_tags':'SELECT ot.* FROM object_tags ot JOIN objects o ON o.id=ot.object_id',
    'relation_evidence':'SELECT e.* FROM relation_evidence e JOIN relations r ON r.id=e.relation_id',
    'canvas_items':'SELECT i.* FROM canvas_items i JOIN canvases c ON c.id=i.canvas_id',
    'canvas_edges':'SELECT e.* FROM canvas_edges e JOIN canvases c ON c.id=e.canvas_id',
    'session_objects':'SELECT so.* FROM session_objects so JOIN learning_sessions s ON s.id=so.session_id',
    'run_artifacts':'SELECT a.* FROM run_artifacts a JOIN experiment_runs r ON r.id=a.run_id',
    'object_attachments':'SELECT oa.* FROM object_attachments oa JOIN objects o ON o.id=oa.object_id',
    'object_revisions':'SELECT r.* FROM object_revisions r JOIN objects o ON o.id=r.object_id',
    'canvas_revisions':'SELECT r.* FROM canvas_revisions r JOIN canvases c ON c.id=r.canvas_id',
    'learning_paths':'SELECT * FROM learning_paths WHERE workspace_id=current_setting(\'app.workspace_id\')::uuid',
    'learning_path_steps':'SELECT s.* FROM learning_path_steps s JOIN learning_paths p ON p.id=s.path_id WHERE p.workspace_id=current_setting(\'app.workspace_id\')::uuid'
}

@app.get('/api/export')
def export_backup():
    output = io.BytesIO()
    with db('REPEATABLE READ') as cursor:
        tables = {}
        for table in TABLES:
            if table in EXPORT_QUERIES:
                cursor.execute(EXPORT_QUERIES[table])
            else:
                cursor.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(table)))
            rows=jsonable_encoder(cursor.fetchall())
            for row in rows:
                for field in ['workspace_id','created_by','updated_by','author_id']:
                    row.pop(field,None)
            tables[table] = rows
        manifest = {'format':'embodied-knowledge','version':3,'created_at':datetime.now().isoformat(),'tables':tables,'external_artifacts_included':False}
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
            (version == 2 and table_names == set(BACKUP_V2_TABLES)) or
            (version == 3 and table_names == set(TABLES))
        ):
            raise HTTPException(422,'备份格式或版本不支持。')
        tables = manifest['tables']
        if version == 1:
            tables['source_imports']=[]
        if version in (1,2):
            tables['learning_paths']=[]
            tables['learning_path_steps']=[]
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
