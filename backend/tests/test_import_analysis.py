import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from fastapi import FastAPI
import pytest

import backend.app as workspace
from backend import import_analysis as analysis


@pytest.fixture
def client():
    # Handler unit tests: keep authentication in the database integration suite.
    app = FastAPI()
    app.add_api_route('/api/source-imports/analyze', workspace.analyze_source, methods=['POST'])
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize('body,language,summary', [('English material about SLAM.', 'en', 'English findings'),
    ('这篇文献研究定位方法。', 'zh', '中文结论'), ('Eine Studie zur Lokalisierung.', 'de', 'Deutsche Ergebnisse')])
def test_analysis_detects_document_language_not_interface_and_never_writes(client, monkeypatch, body, language, summary):
    calls=[]
    monkeypatch.setattr(analysis.llm,'require_configuration',lambda: SimpleNamespace())
    async def complete(config,messages):
        calls.extend(messages)
        return {'content':json.dumps({'language':language,'summary':summary,'analysis_md':'## Methods\nEvidence'}), 'model':'test-model','usage':{},'finish_reason':'stop'}
    monkeypatch.setattr(analysis.llm,'complete',complete)
    monkeypatch.setattr(workspace,'db',lambda:pytest.fail('Analysis must not access the database'))
    response=client.post('/api/source-imports/analyze',json={'title':'Original title','body_md':body})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['language']==language and data['summary']==summary
    assert data['provenance']['excerpted'] is False
    assert data['provenance']['source_characters']==len(body)
    assert json.loads(calls[1]['content'])['material']==body
    assert 'predominant language' in calls[0]['content']
    assert 'untrusted data' in calls[0]['content']


def test_long_material_reports_partial_coverage():
    text='A'*20000+'B'*20000+'C'*20000+'D'*20000
    selected,partial=analysis.excerpt(text)
    assert partial and selected.startswith('A'*16000) and selected.endswith('D'*16000)
    assert 'B' in selected and 'C' in selected
    assert len(selected)<analysis.LIMIT+100


@pytest.mark.parametrize('content,reason', [('not json','stop'), ('[]','stop'),
    (json.dumps({'language':'en','summary':'s','analysis_md':'x'}),'length'),
    (json.dumps({'language':'en','summary':'s','analysis_md':'![x](import-asset://bad)'}),'stop')])
def test_invalid_or_truncated_results_do_not_replace_draft(client, monkeypatch, content, reason):
    monkeypatch.setattr(analysis.llm,'require_configuration',lambda:None)
    async def complete(*args):
        return {'content':content,'finish_reason':reason,'model':'test'}
    monkeypatch.setattr(analysis.llm,'complete',complete)
    response=client.post('/api/source-imports/analyze',json={'title':'Paper','body_md':'Original text'})
    assert response.status_code==502
