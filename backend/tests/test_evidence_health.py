"""Evidence health checks: what they report, what they leave out, who may see them, and that they only read."""
from datetime import date
from itertools import product
import random
import threading

import pytest

from backend import evidence_health, link_checker
from helpers import DSN, wait_for_job

pytestmark = pytest.mark.skipif(not DSN, reason='Only run against an isolated test database.')


def obj(client, title, kind='concept', **extra):
    response = client.post('/api/objects', json={'title': title, 'kind': kind, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def relate(client, source, target, relation_type='uses', evidence=None):
    response = client.post('/api/relations', json={'source_id': source['id'], 'target_id': target['id'], 'relation_type': relation_type, 'evidence': evidence or []})
    assert response.status_code == 201, response.text
    return response.json()


def findings(client, check, **params):
    response = client.get(f'/api/evidence-health/{check}', params=params)
    assert response.status_code == 200, response.text
    assert int(response.headers['X-Total-Count']) == response.json()['total']
    return response.json()


def coded(client, check, **params):
    """(code, params) of every finding: what the interface renders in the user's language."""
    return [(item['code'], item['params']) for item in findings(client, check, **params)['findings']]


def summary(client, **params):
    response = client.get('/api/evidence-health', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_relations_without_evidence_and_coverage(client):
    a, b, c, d = (obj(client, name) for name in ['甲', '乙', '丙', '丁'])
    bare = relate(client, a, b)
    relate(client, a, c, evidence=[{'source_url': 'https://example.com/1', 'locator': '第 3 节'}])
    relate(client, b, c, evidence=[{'source_url': 'https://example.com/2'}])
    relate(client, c, d, evidence=[{'evidence_object_id': a['id'], 'locator': 'p.2'}])
    state = summary(client)
    assert state['coverage'] == {'relations': 4, 'with_evidence': 3, 'with_locator': 2, 'percent': 75.0}
    assert coded(client, 'relations_without_evidence') == [('relation_no_evidence', {'source': '甲', 'relation': 'uses', 'target': '乙'})]
    assert coded(client, 'evidence_without_locator') == [('evidence_no_locator', {'source': '乙', 'relation': 'uses', 'target': '丙'})]
    assert findings(client, 'relations_without_evidence')['findings'][0]['message'] == '《甲》使用《乙》：没有任何证据。'
    assert {check['id']: check['count'] for check in state['checks']}['relations_without_evidence'] == 1
    assert state['totals'] == {'error': 0, 'warning': 1, 'info': 1}
    assert client.patch(f"/api/objects/{d['id']}", json={**d, 'archived_at': '2026-10-01T00:00:00Z'}).status_code == 200   # archived endpoints are ignored
    assert summary(client)['coverage']['relations'] == 3
    client.delete(f"/api/relations/{bare['id']}")
    assert findings(client, 'relations_without_evidence')['total'] == 0


def test_invalid_evidence(client):
    a, b, proof = obj(client, '甲'), obj(client, '乙'), obj(client, '证据笔记')
    relate(client, a, b, evidence=[{'evidence_object_id': proof['id'], 'locator': '1'}])
    relate(client, b, a, 'supports', evidence=[{'source_url': 'javascript:alert(1)', 'locator': '1'}, {'source_url': 'https://ok.example/', 'locator': '1'}])
    assert [code for code, _ in coded(client, 'invalid_evidence')] == ['evidence_bad_url']
    client.delete(f"/api/objects/{proof['id']}")
    result = dict(coded(client, 'invalid_evidence'))
    assert set(result) == {'evidence_bad_url', 'evidence_object_deleted'}
    assert result['evidence_object_deleted'] == {'source': '甲', 'relation': 'uses', 'target': '乙', 'evidence': '证据笔记'}
    assert result['evidence_bad_url']['url'] == 'javascript:alert(1)'
    assert summary(client)['totals']['error'] == 2


@pytest.fixture
def links(monkeypatch):
    """Replace network access: URL -> outcome. Records every URL asked for."""
    asked, table = [], {}

    def fake(url, *args, **kwargs):
        asked.append(url)
        return table.get(url, {'status_code': 200, 'ok': True, 'error': None, 'final_url': None})
    monkeypatch.setattr(link_checker, 'check_url', fake)
    return asked, table


def test_link_check_job_stores_results_and_dead_links_become_findings(client, links):
    asked, table = links
    dead = {'status_code': 404, 'ok': False, 'error': 'not_found', 'final_url': None}
    unclear = {'status_code': 403, 'ok': None, 'error': 'restricted', 'final_url': None}
    table.update({'https://dead.example/a': dead, 'https://dead.example/e': dead, 'https://login.example/': unclear})
    a = obj(client, '有死链的笔记', 'resource', source_url='https://dead.example/a')
    b = obj(client, '好笔记', 'resource', source_url='https://fine.example/')
    obj(client, '登录页', 'resource', source_url='https://login.example/')
    gone = obj(client, '已归档', 'resource', source_url='https://archived.example/')
    client.patch(f"/api/objects/{gone['id']}", json={**gone, 'archived_at': '2026-10-01T00:00:00Z'})
    obj(client, '内部', 'resource', source_url='not a url')
    relate(client, a, b, evidence=[{'source_url': 'https://dead.example/e', 'locator': '1'}, {'source_url': 'https://fine.example/'}])
    before = summary(client)['links']
    assert before['distinct_urls'] == 4 and before['checked'] == 0 and before['last_checked_at'] is None
    started = client.post('/api/evidence-health/link-check')
    assert started.status_code == 202
    job = wait_for_job(client, started.json()['job_id'])
    assert job['status'] == 'succeeded' and job['result'] == {'checked': 4, 'dead': 2, 'unclear': 1, 'reachable': 1}
    assert sorted(asked) == ['https://dead.example/a', 'https://dead.example/e', 'https://fine.example/', 'https://login.example/']   # archived and malformed ones are not checked
    after = summary(client)
    assert after['links']['checked'] == 4 and after['links']['dead'] == 2 and after['links']['unclear'] == 1 and after['links']['last_checked_at']
    result = findings(client, 'dead_links')
    assert result['total'] == 2
    by_url = {item['params']['url']: item for item in result['findings']}
    assert by_url['https://dead.example/a']['code'] == 'link_dead' and by_url['https://dead.example/a']['params'] == {'url': 'https://dead.example/a', 'error': 'not_found', 'status': 404, 'objects': 1, 'evidence': 0}
    assert [o['title'] for o in by_url['https://dead.example/a']['objects']] == ['有死链的笔记'] and by_url['https://dead.example/e']['params']['evidence'] == 1
    assert '1 条证据' in by_url['https://dead.example/e']['message']
    asked.clear()
    assert wait_for_job(client, client.post('/api/evidence-health/link-check').json()['job_id'])['result']['checked'] == 0   # checked recently, nothing to do
    assert wait_for_job(client, client.post('/api/evidence-health/link-check?force=true').json()['job_id'])['result']['checked'] == 4
    table['https://dead.example/a'] = {'status_code': 200, 'ok': True, 'error': None, 'final_url': None}
    wait_for_job(client, client.post('/api/evidence-health/link-check?force=true').json()['job_id'])
    assert findings(client, 'dead_links')['total'] == 1


def test_only_one_link_check_runs_at_a_time(client, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(link_checker, 'check_url', lambda url, *a, **k: (release.wait(10), {'status_code': 200, 'ok': True, 'error': None, 'final_url': None})[1])
    obj(client, '笔记', 'resource', source_url='https://slow.example/')
    first = client.post('/api/evidence-health/link-check')
    second = client.post('/api/evidence-health/link-check')
    assert first.status_code == 202 and second.status_code == 200 and second.json()['already_running'] and second.json()['job_id'] == first.json()['job_id']
    release.set()
    assert wait_for_job(client, first.json()['job_id'])['status'] == 'succeeded'


def test_a_broken_network_does_not_turn_every_link_into_a_dead_link(client, monkeypatch):
    monkeypatch.setattr(link_checker, 'check_url', lambda url, *a, **k: {'status_code': None, 'ok': False, 'error': 'connect_failed', 'final_url': None})
    for index in range(6):
        obj(client, f'笔记{index}', 'resource', source_url=f'https://site{index}.example/')
    job = wait_for_job(client, client.post('/api/evidence-health/link-check').json()['job_id'])
    assert job['status'] == 'failed' and '网络' in job['error']
    assert summary(client)['links']['checked'] == 0 and findings(client, 'dead_links')['total'] == 0


def test_stale_and_undated_sources(client):
    old = obj(client, '老资料', 'resource', source_url='https://a.example/', metadata={'verified_on': '2020-01-01'})
    obj(client, '新资料', 'repository', source_url='https://b.example/', metadata={'verified_on': date.today().isoformat()})
    obj(client, '没日期的论文', 'resource', source_url='https://c.example/')
    obj(client, '日期写错了', 'model', source_url='https://d.example/', metadata={'verified_on': '2026-02-31'})
    obj(client, '概念不算外部资料', 'concept', source_url='https://e.example/', metadata={'verified_on': '2020-01-01'})
    obj(client, '没有来源地址', 'resource', metadata={'verified_on': '2020-01-01'})
    result = findings(client, 'stale_sources', stale_days=180)
    assert result['total'] == 3 and [(item['severity'], item['code']) for item in result['findings']] == [('warning', 'source_stale'), ('info', 'source_undated'), ('info', 'source_undated')]
    first = result['findings'][0]
    assert first['params'] == {'title': '老资料', 'verified_on': '2020-01-01', 'age_days': first['detail']['age_days'], 'stale_days': 180}
    assert first['detail']['age_days'] > 2000 and old['id'] == first['objects'][0]['id']
    assert findings(client, 'stale_sources', stale_days=100000)['total'] == 2
    state = {check['id']: check for check in summary(client, stale_days=180)['checks']}['stale_sources']
    assert state['count'] == 3 and state['by_severity'] == {'warning': 1, 'info': 2}


def test_dependency_cycles(client):
    a, b, c, x, y, d, e = (obj(client, name) for name in 'abcxyde')
    for left, right in [(a, b), (b, c), (c, a), (x, y), (y, x), (d, e)]:
        relate(client, left, right, 'depends_on')
    relate(client, a, d, 'uses')
    relate(client, d, a, 'uses')           # a cycle, but not of prerequisites
    result = findings(client, 'dependency_cycles')
    assert result['total'] == 2
    paths = [item['params']['path'] for item in result['findings']]
    assert 'a → b → c → a' in paths and 'x → y → x' in paths
    big = next(item for item in result['findings'] if item['detail']['size'] == 3)
    assert [o['title'] for o in big['objects']] == ['a', 'b', 'c']
    assert client.patch(f"/api/objects/{c['id']}", json={**c, 'archived_at': '2026-10-01T00:00:00Z'}).status_code == 200
    assert findings(client, 'dependency_cycles')['total'] == 1


def test_strongly_connected_components_match_a_brute_force_definition():
    rng = random.Random(3)
    for _ in range(60):
        nodes = [str(i) for i in range(rng.randint(2, 11))]
        edges = list({(a, b) for a, b in product(nodes, nodes) if a != b and rng.random() < 0.18})
        reach = {a: {a} for a in nodes}
        changed = True
        while changed:
            changed = False
            for a, b in edges:
                new = reach[b] - reach[a]
                if new:
                    reach[a] |= new
                    changed = True
        expected = {frozenset(b for b in nodes if a in reach[b] and b in reach[a]) for a in nodes}
        expected = {group for group in expected if len(group) > 1}
        assert {frozenset(group) for group in evidence_health.strongly_connected(edges)} == expected, edges
    long_chain = [(str(i), str(i + 1)) for i in range(20000)]
    assert evidence_health.strongly_connected(long_chain) == []          # no recursion limit problems on long chains
    assert [len(group) for group in evidence_health.strongly_connected(long_chain + [('20000', '0')])] == [20001]


def test_contested_claims(client):
    claim, other = obj(client, '某个结论'), obj(client, '没争议的结论')
    pro1, pro2, con = obj(client, '支持者一'), obj(client, '支持者二'), obj(client, '质疑者')
    relate(client, pro1, claim, 'supports')
    relate(client, pro2, claim, 'supports')
    assert findings(client, 'contested_claims')['total'] == 0
    relate(client, con, claim, 'questions')
    relate(client, pro1, other, 'supports')
    result = findings(client, 'contested_claims')
    assert result['total'] == 1 and result['findings'][0]['params'] == {'title': '某个结论', 'supporters': 2, 'questioners': 1}
    assert result['findings'][0]['message'] == '《某个结论》被 2 个来源支持，也被 1 个来源质疑。'
    assert [s['title'] for s in result['findings'][0]['detail']['supporters']] == ['支持者一', '支持者二'] and result['findings'][0]['detail']['questioners'][0]['title'] == '质疑者'
    assert result['findings'][0]['severity'] == 'info'


def run(client, experiment, status='planned', **extra):
    response = client.post('/api/runs', json={'experiment_id': experiment['id'], 'status': status, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_unverified_experiment_claims(client):
    question, model, other = obj(client, '待验证问题', 'question'), obj(client, '模型', 'model'), obj(client, '数据集', 'dataset')
    no_runs, planned, succeeded, failed = (obj(client, name, 'experiment') for name in ['无运行的实验', '只计划的实验', '成功的实验', '失败的实验'])
    for experiment, target, kind in [(no_runs, question, 'supports'), (planned, model, 'evaluates'), (succeeded, question, 'questions'), (failed, other, 'evaluates')]:
        relate(client, experiment, target, kind)
    relate(client, question, no_runs, 'related_to')                      # not a claim made by the experiment
    run(client, planned)
    good = run(client, succeeded, 'succeeded')
    run(client, failed, 'failed')
    result = coded(client, 'unverified_experiment_claims')
    assert all(code == 'claim_experiment_unverified' for code, _ in result)
    assert sorted((p['experiment'], p['relation'], p['target']) for _, p in result) == sorted([('无运行的实验', 'supports', '待验证问题'), ('只计划的实验', 'evaluates', '模型'), ('失败的实验', 'evaluates', '数据集')])
    client.delete(f"/api/runs/{good['id']}")                              # a deleted run proves nothing
    assert findings(client, 'unverified_experiment_claims')['total'] == 4


def test_mastery_claims_need_a_successful_linked_experiment(client):
    claimed = obj(client, '声称能复现', 'model', mastery_status='reproduce')
    implemented = obj(client, '声称能实现', 'model', mastery_status='implement')
    backed = obj(client, '有成功实验支撑', 'model', mastery_status='reproduce')
    reverse = obj(client, '关系方向相反', 'model', mastery_status='implement')
    explained = obj(client, '只说能解释', 'model', mastery_status='explain')
    experiment, planned = obj(client, '成功的实验', 'experiment'), obj(client, '只计划的实验', 'experiment')
    run(client, experiment, 'succeeded')
    run(client, planned)
    relate(client, experiment, backed, 'evaluates')
    relate(client, reverse, experiment, 'uses')
    relate(client, planned, claimed, 'evaluates')
    mastery = sorted((p['title'], p['claim']) for code, p in coded(client, 'unverified_experiment_claims') if code == 'claim_mastery_unverified')
    assert mastery == [('声称能复现', 'reproduce'), ('声称能实现', 'implement')]
    assert '“能复现”' in next(i['message'] for i in findings(client, 'unverified_experiment_claims')['findings'] if i['params'].get('claim') == 'reproduce')
    assert implemented['id'] and explained['id']


def test_incomplete_runs(client):
    experiment = obj(client, '实验', 'experiment')
    complete = {'command': 'python run.py', 'git_commit': 'abc123', 'config': {'batch': 1}, 'metrics': {'loss': 0.1}}
    run(client, experiment, 'succeeded', **complete)
    bare = run(client, experiment, 'succeeded')
    run(client, experiment, 'succeeded', **{**complete, 'git_commit': '  ', 'metrics': {}})
    run(client, experiment, 'failed', failure_md='显存不足')
    run(client, experiment, 'failed')
    run(client, experiment, 'planned')
    gone = run(client, experiment, 'succeeded')
    client.delete(f"/api/runs/{gone['id']}")
    result = findings(client, 'incomplete_runs')
    assert result['total'] == 3
    by_run = {item['detail']['run_id']: item for item in result['findings']}
    assert by_run[bare['id']]['params'] == {'experiment': '实验', 'status': 'succeeded', 'missing': ['command', 'git_commit', 'config', 'metrics']}
    assert '缺少：运行命令、代码提交（commit）、配置、指标' in by_run[bare['id']]['message']
    assert sorted(item['params']['missing'][0] for item in result['findings'] if len(item['params']['missing']) == 1) == ['failure_md']
    assert any(item['params']['missing'] == ['git_commit', 'metrics'] for item in result['findings'])


def test_paging_unknown_checks_and_read_only(client):
    hub = obj(client, '中心')
    for index in range(7):
        relate(client, hub, obj(client, f'叶子{index}'))
    page_one, page_two = findings(client, 'relations_without_evidence', limit=5), findings(client, 'relations_without_evidence', limit=5, offset=5)
    keys = [item['key'] for item in page_one['findings'] + page_two['findings']]
    assert page_one['total'] == 7 and len(page_one['findings']) == 5 and len(page_two['findings']) == 2 and len(set(keys)) == 7
    assert findings(client, 'relations_without_evidence', offset=500)['findings'] == []
    assert client.get('/api/evidence-health/not_a_check').status_code == 404
    assert [check['id'] for check in summary(client)['checks']] == [check.id for check in evidence_health.CHECKS]
    before = [client.get(path).json() for path in ('/api/objects', '/api/relations', '/api/runs')]
    summary(client)
    for check in evidence_health.CHECKS:
        findings(client, check.id)
    assert before == [client.get(path).json() for path in ('/api/objects', '/api/relations', '/api/runs')]
    assert summary(client, stale_days=0)['stale_days'] == 1 and summary(client, stale_days=999999)['stale_days'] == 3650


def test_every_message_code_has_a_chinese_sentence_and_params_that_fit_it():
    sample = {'source': 'A', 'relation': 'uses', 'target': 'B', 'evidence': 'E', 'url': 'u', 'error': 'not_found', 'status': 404, 'objects': 1, 'experiment': 'X', 'title': 'T',
              'claim': 'reproduce', 'missing': ['command'], 'verified_on': '2020-01-01', 'age_days': 9, 'stale_days': 1, 'path': 'a → b', 'supporters': 1, 'questioners': 1}
    for code in evidence_health.MESSAGES:
        params = {**sample, 'status': 'failed'} if code == 'run_incomplete' else sample
        assert evidence_health.zh_message(code, params)
