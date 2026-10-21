import copy
import json
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.path_artifacts import MAX_BYTES, import_artifact, make_artifact, parse_artifact, validate_artifact


def example():
    a, b = str(uuid4()), str(uuid4())
    return {'format': 'zhixing-learning-path', 'version': 1, 'created_at': '2026-10-22T00:00:00Z',
        'includes_body': True,
        'path': {'id': str(uuid4()), 'title': '科研学习路径', 'objective_md': 'Explain the method',
            'description_md': '中文与 English', 'completion_criteria_md': 'Show evidence',
            'steps': [{'id': str(uuid4()), 'object_id': identifier, 'title': title, 'guidance_md': 'Read and explain',
                'completion_criteria_md': 'Explain independently', 'estimated_minutes': 10}
                for identifier, title in [(a, '概念'), (b, '论文')]]},
        'objects': [{'id': identifier, 'kind': 'concept', 'title': title, 'summary': 'Summary',
            'body_md': 'Original $x$ </script> text', 'source_url': 'https://example.org/paper',
            'tags': ['研究'], 'metadata': {'doi': '10.1234/example'}} for identifier, title in [(a, '概念'), (b, '论文')]],
        'relations': [{'id': str(uuid4()), 'source_id': a, 'target_id': b, 'relation_type': 'uses',
            'description': 'Method evidence', 'evidence': [{'evidence_object_id': b,
                'source_url': 'https://example.org/paper', 'locator': 'p. 3', 'explanation': 'Supports the method'}]}]}


def test_json_and_inert_html_roundtrip_preserves_original_content():
    value = example()
    encoded = json.dumps(value, ensure_ascii=False).encode()
    assert parse_artifact(encoded)['objects'][0]['body_md'] == value['objects'][0]['body_md']
    payload = json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')
    html = f'''<!doctype html><html><script>throw Error('never executed')</script>
        <script type="application/json" id="zhixing-learning-path">{payload}</script></html>'''
    assert parse_artifact(html.encode()) == parse_artifact(encoded)


@pytest.mark.parametrize('change', [
    lambda value: value.update(version=2),
    lambda value: value.update(credentials={'api_key': 'forbidden'}),
    lambda value: value['objects'].append(copy.deepcopy(value['objects'][0])),
    lambda value: value['relations'][0].update(target_id=str(uuid4())),
    lambda value: value['relations'][0]['evidence'][0].update(evidence_object_id=str(uuid4())),
    lambda value: value['objects'][0].update(source_url='javascript:alert(1)'),
    lambda value: value['objects'][0].update(source_url='https://user:password@example.org'),
    lambda value: value['objects'][0].update(metadata={'api_key': 'forbidden'}),
    lambda value: value['path']['steps'][0].update(title='   '),
    lambda value: value.update(includes_body=False),
])
def test_invalid_or_overbroad_snapshots_are_rejected(change):
    value = example()
    change(value)
    with pytest.raises(HTTPException) as failure:
        validate_artifact(value)
    assert failure.value.status_code == 422
    assert failure.value.detail == 'artifact.invalid'


def test_limits_and_duplicate_embedded_payloads():
    with pytest.raises(HTTPException) as failure:
        parse_artifact(b' ' * (MAX_BYTES + 1))
    assert failure.value.status_code == 413
    for content in (b'invalid', b'\xff', b'[]', b'<html>nothing</html>',
                    b'<script id="zhixing-learning-path" type="application/json">{}</script>' * 2):
        with pytest.raises(HTTPException) as failure:
            parse_artifact(content)
        assert failure.value.status_code == 422


class SnapshotCursor:
    def __init__(self, value, workspace):
        self.value = value
        self.workspace = workspace
        self.rows = []
        self.queries = []

    def execute(self, statement, params):
        self.queries.append((statement, params))
        if 'FROM objects' in statement:
            assert 'workspace_id=%s' in statement and params[1] == self.workspace
            self.rows = [dict(row) for row in self.value['objects']]
        elif 'FROM tags' in statement:
            self.rows = [{'name': '研究'}]
        elif 'FROM relations' in statement:
            assert 'workspace_id=%s' in statement and params[0] == self.workspace
            self.rows = [{key: val for key, val in row.items() if key != 'evidence'} for row in self.value['relations']]
        elif 'FROM relation_evidence' in statement:
            self.rows = copy.deepcopy(self.value['relations'][0]['evidence'])

    def fetchall(self):
        return self.rows


def test_snapshot_projection_excludes_credentials_other_evidence_and_private_fields():
    value = example()
    workspace = str(uuid4())
    value['objects'][0]['metadata']['api_key'] = 'private-key'
    value['relations'][0]['evidence'].append({'evidence_object_id': str(uuid4()),
        'source_url': None, 'locator': 'private', 'explanation': 'private evidence'})
    doc = {**value['path'], 'workspace_id': workspace, 'created_by': str(uuid4()), 'share_token': 'private-token'}
    result = make_artifact(SnapshotCursor(value, workspace), doc)
    text = json.dumps(result)
    assert 'private-key' not in text and 'private-token' not in text and 'private evidence' not in text
    assert 'workspace_id' not in text and 'created_by' not in text
    assert all(obj['body_md'] == '' for obj in result['objects'])
    assert result['objects'][0]['metadata'] == {'doi': '10.1234/example'}
    assert len(result['relations'][0]['evidence']) == 1


def test_import_allocates_new_ids_and_rewrites_local_references_without_overwriting():
    value = example()
    a = value['objects'][0]['id']
    value['objects'][1]['body_md'] = f'[Concept](/knowledge/{a})'
    queries = []
    class Cursor:
        def execute(self, statement, params): queries.append((statement, params))
    workspace = str(uuid4())
    tags = []
    identifier = import_artifact(Cursor(), value, workspace, lambda cursor, identifier, values: tags.append((identifier, values)))
    assert identifier != value['path']['id']
    assert all(statement.strip().startswith('INSERT') for statement, params in queries)
    objects = [params for statement, params in queries if 'INSERT INTO objects' in statement]
    assert all(params[1] == workspace for params in objects)
    assert objects[0][0] != a
    assert f'/knowledge/{objects[0][0]}' in objects[1][5]
    assert f'/knowledge/{a}' not in objects[1][5]
    relation = next(params for statement, params in queries if 'INSERT INTO relations' in statement)
    assert relation[2:4] == (objects[0][0], objects[1][0])
    steps = [params for statement, params in queries if 'INSERT INTO learning_path_steps' in statement]
    assert [step[2] for step in steps] == [obj[0] for obj in objects]
    assert all(step[1] == identifier for step in steps)
    assert len(tags) == 2
