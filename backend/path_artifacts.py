"""Portable, workspace-scoped learning snapshots. No credentials or attachments."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import re
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from psycopg2.extras import Json

MAX_BYTES = 8 * 1024 * 1024
PAYLOAD_ID = 'zhixing-learning-path'
METADATA_KEYS = {'subtype', 'doi', 'arxiv', 'authors', 'year', 'commit', 'weight_version', 'dataset_version', 'inputs', 'outputs'}


def portable_metadata(value):
    return isinstance(value, str) and len(value) <= 10000 or type(value) is int or (
        isinstance(value, list) and len(value) <= 100 and all(isinstance(item, str) and len(item) <= 1000 for item in value))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Evidence(StrictModel):
    evidence_object_id: UUID | None = None
    source_url: str | None = Field(default=None, max_length=4000)
    locator: str = Field(default='', max_length=10000)
    explanation: str = Field(default='', max_length=50000)

    @field_validator('source_url')
    @classmethod
    def safe_url(cls, value):
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Invalid source URL')
        return value


class ArtifactObject(StrictModel):
    id: UUID
    kind: Literal['concept', 'resource', 'repository', 'model', 'dataset', 'benchmark', 'experiment', 'question', 'task']
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(default='', max_length=50000)
    body_md: str = Field(default='', max_length=1000000)
    source_url: str | None = Field(default=None, max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    metadata: dict = Field(default_factory=dict)
    _safe_url = field_validator('source_url')(Evidence.safe_url.__func__)

    @field_validator('tags')
    @classmethod
    def tag_lengths(cls, value):
        if any(len(tag) > 200 for tag in value):
            raise ValueError('Tag too long')
        return value

    @field_validator('metadata')
    @classmethod
    def metadata_fields(cls, value):
        if not set(value).issubset(METADATA_KEYS) or not all(portable_metadata(item) for item in value.values()):
            raise ValueError('Invalid metadata')
        return value


class ArtifactRelation(StrictModel):
    id: UUID
    source_id: UUID
    target_id: UUID
    relation_type: Literal['depends_on', 'implements', 'uses', 'evaluates', 'supports', 'questions', 'compares_with', 'related_to']
    description: str = Field(default='', max_length=50000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100)


class ArtifactStep(StrictModel):
    id: UUID
    object_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    guidance_md: str = Field(default='', max_length=200000)
    completion_criteria_md: str = Field(default='', max_length=200000)
    estimated_minutes: int | None = Field(default=None, ge=0, le=100000)


class ArtifactPath(StrictModel):
    id: UUID
    title: str = Field(min_length=1, max_length=500)
    objective_md: str = Field(default='', max_length=200000)
    description_md: str = Field(default='', max_length=200000)
    completion_criteria_md: str = Field(default='', max_length=200000)
    steps: list[ArtifactStep] = Field(max_length=100)


class PathArtifact(StrictModel):
    format: Literal['zhixing-learning-path']
    version: Literal[1]
    created_at: datetime
    includes_body: bool = False
    path: ArtifactPath
    objects: list[ArtifactObject] = Field(max_length=100)
    relations: list[ArtifactRelation] = Field(max_length=1000)

    @model_validator(mode='after')
    def references(self):
        for rows in (self.objects, self.relations, self.path.steps):
            if len({row.id for row in rows}) != len(rows):
                raise ValueError('Duplicate ID')
        objects = {row.id for row in self.objects}
        selected = {step.object_id for step in self.path.steps if step.object_id is not None}
        if selected != objects:
            raise ValueError('Steps and objects do not match')
        keys = set()
        for relation in self.relations:
            if relation.source_id not in objects or relation.target_id not in objects or relation.source_id == relation.target_id:
                raise ValueError('Invalid relationship endpoints')
            ends = (relation.source_id, relation.target_id)
            if relation.relation_type in ('related_to', 'compares_with'):
                ends = tuple(sorted(ends))
            key = (*ends, relation.relation_type)
            if key in keys:
                raise ValueError('Duplicate relationship')
            keys.add(key)
            for evidence in relation.evidence:
                if evidence.evidence_object_id is not None and evidence.evidence_object_id not in objects:
                    raise ValueError('Evidence outside snapshot')
                if evidence.evidence_object_id is None and not evidence.source_url:
                    raise ValueError('Evidence has no source')
        if any(not row.title.strip() for row in [self.path, *self.path.steps, *self.objects]):
            raise ValueError('Blank title')
        if not self.includes_body and any(obj.body_md for obj in self.objects):
            raise ValueError('Unexpected full text')
        return self


class PayloadParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.matches = 0
        self.data = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == 'script' and attrs.get('id') == PAYLOAD_ID and attrs.get('type') == 'application/json':
            self.matches += 1
            self.inside = True

    def handle_endtag(self, tag):
        if tag.lower() == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.data.append(data)


def validate_artifact(value):
    try:
        return PathArtifact.model_validate(value).model_dump(mode='json')
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(422, 'artifact.invalid') from None


def parse_artifact(content):
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'artifact.tooLarge')
    try:
        text = content.decode('utf-8-sig')
        if not text.lstrip().startswith('{'):
            parser = PayloadParser()
            parser.feed(text)
            parser.close()
            if parser.matches != 1:
                raise ValueError('Missing or duplicate payload')
            text = ''.join(parser.data)
        return validate_artifact(json.loads(text))
    except HTTPException:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise HTTPException(422, 'artifact.invalid') from None


def make_artifact(cursor, document, include_body=False):
    """Project only objects selected in this path and their mutual relationships."""
    ids = list(dict.fromkeys(str(step['object_id']) for step in document['steps'] if step.get('object_id')))
    workspace = str(document['workspace_id'])
    objects = []
    relations = []
    if ids:
        cursor.execute('''SELECT id,kind,title,summary,body_md,source_url,metadata FROM objects
            WHERE id=ANY(%s::uuid[]) AND workspace_id=%s AND deleted_at IS NULL''', (ids, workspace))
        objects = [dict(row) for row in cursor.fetchall()]
        for obj in objects:
            obj['id'] = str(obj['id'])
            obj['body_md'] = obj['body_md'] if include_body else ''
            obj['metadata'] = {key:value for key,value in obj.get('metadata',{}).items() if key in METADATA_KEYS and portable_metadata(value)}
            # Source URLs are optional; do not export local file paths or URL credentials.
            try:
                obj['source_url'] = Evidence.safe_url(obj['source_url'])
            except ValueError:
                obj['source_url'] = None
            cursor.execute('SELECT t.name FROM tags t JOIN object_tags ot ON ot.tag_id=t.id WHERE ot.object_id=%s ORDER BY t.name', (obj['id'],))
            obj['tags'] = [row['name'] for row in cursor.fetchall()]
        selected = {obj['id'] for obj in objects}
        cursor.execute('''SELECT id,source_id,target_id,relation_type,description FROM relations
            WHERE workspace_id=%s AND source_id=ANY(%s::uuid[]) AND target_id=ANY(%s::uuid[])
            AND deleted_at IS NULL ORDER BY id''', (workspace, list(selected), list(selected)))
        for row in cursor.fetchall():
            relation = {**dict(row), 'evidence': []}
            for field in ('id', 'source_id', 'target_id'):
                relation[field] = str(relation[field])
            cursor.execute('SELECT evidence_object_id,source_url,locator,explanation FROM relation_evidence WHERE relation_id=%s ORDER BY id', (relation['id'],))
            for item in cursor.fetchall():
                evidence = dict(item)
                evidence['evidence_object_id'] = str(item['evidence_object_id']) if item['evidence_object_id'] and str(item['evidence_object_id']) in selected else None
                try:
                    evidence['source_url'] = Evidence.safe_url(item['source_url'])
                except ValueError:
                    evidence['source_url'] = None
                if evidence['evidence_object_id'] or evidence['source_url']:
                    relation['evidence'].append(evidence)
            relations.append(relation)
        order = {identifier: index for index, identifier in enumerate(ids)}
        objects.sort(key=lambda obj: order[obj['id']])
    selected = {obj['id'] for obj in objects}
    path = {field: str(document[field]) if field == 'id' else document[field] for field in
            ('id', 'title', 'objective_md', 'description_md', 'completion_criteria_md')}
    path['steps'] = [{
        'id': str(step['id']), 'object_id': str(step['object_id']) if str(step.get('object_id')) in selected else None,
        **{field: step.get(field) for field in ('title', 'guidance_md', 'completion_criteria_md', 'estimated_minutes')}
    } for step in document['steps']]
    artifact = validate_artifact({'format': 'zhixing-learning-path', 'version': 1,
        'created_at': datetime.now(timezone.utc), 'includes_body': include_body,
        'path': path, 'objects': objects, 'relations': relations})
    if len(json.dumps(artifact, ensure_ascii=False).encode('utf-8')) > MAX_BYTES:
        raise HTTPException(413, 'artifact.tooLarge')
    return artifact


def import_artifact(cursor, artifact, workspace_id, set_tags):
    """Create independent copies atomically. Never merge on foreign IDs or titles."""
    artifact = validate_artifact(artifact)
    mapping = {obj['id']: str(uuid4()) for obj in artifact['objects']}
    def remap_text(text):
        return re.sub(r'(?<![\w:/])(/knowledge/)([0-9a-fA-F-]{36})(?![\w-])',
                      lambda match: match[1] + mapping.get(match[2].lower(), match[2]), text or '')
    for obj in artifact['objects']:
        cursor.execute('''INSERT INTO objects(id,workspace_id,kind,title,summary,body_md,source_url,metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (mapping[obj['id']], str(workspace_id), obj['kind'],
            obj['title'], obj['summary'], remap_text(obj['body_md']), obj['source_url'], Json(obj['metadata'])))
        set_tags(cursor, mapping[obj['id']], obj['tags'])
    for relation in artifact['relations']:
        identifier = str(uuid4())
        source, target = mapping[relation['source_id']], mapping[relation['target_id']]
        if relation['relation_type'] in ('related_to', 'compares_with'):
            source, target = sorted((source, target))
        cursor.execute('''INSERT INTO relations(id,workspace_id,source_id,target_id,relation_type,description)
            VALUES (%s,%s,%s,%s,%s,%s)''', (identifier, str(workspace_id), source, target,
            relation['relation_type'], remap_text(relation['description'])))
        for evidence in relation['evidence']:
            cursor.execute('''INSERT INTO relation_evidence(relation_id,evidence_object_id,source_url,locator,explanation)
                VALUES (%s,%s,%s,%s,%s)''', (identifier, mapping.get(evidence['evidence_object_id']),
                evidence['source_url'], evidence['locator'], remap_text(evidence['explanation'])))
    identifier = str(uuid4())
    doc = artifact['path']
    cursor.execute('''INSERT INTO learning_paths(id,workspace_id,title,objective_md,description_md,completion_criteria_md)
        VALUES (%s,%s,%s,%s,%s,%s)''', (identifier, str(workspace_id), doc['title'], remap_text(doc['objective_md']),
        remap_text(doc['description_md']), remap_text(doc['completion_criteria_md'])))
    for position, step in enumerate(doc['steps']):
        cursor.execute('''INSERT INTO learning_path_steps
            (id,path_id,object_id,position,title,guidance_md,completion_criteria_md,estimated_minutes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (str(uuid4()), identifier, mapping.get(step['object_id']),
            position, step['title'], remap_text(step['guidance_md']), remap_text(step['completion_criteria_md']), step['estimated_minutes']))
    return identifier
