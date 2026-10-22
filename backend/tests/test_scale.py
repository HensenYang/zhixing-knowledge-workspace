"""Scale behaviour: constant query counts, paging, graph queries, trash and the connection pool."""
from collections import deque
from uuid import uuid4
import random

from fastapi import HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from backend import pool
from helpers import DSN, create

pytestmark = pytest.mark.skipif(not DSN, reason='Only run against an explicitly configured isolated test database.')


@pytest.fixture
def statements(monkeypatch):
    """Record every statement the application runs through its request cursor."""
    seen = []

    class CountingCursor(RealDictCursor):
        def execute(self, query, vars=None):
            seen.append(str(query))
            return super().execute(query, vars)

    monkeypatch.setattr(pool, 'RealDictCursor', CountingCursor)
    return seen


def populate(client, count, start=0):
    """`count` notes with tags, a chain of relations with evidence, sessions, runs and a canvas edge each."""
    notes = [client.post('/api/objects', json={'title': f'规模笔记{start + i:03d}', 'body_md': f'正文{i}', 'tags': ['规模', f'组{i % 3}']}).json() for i in range(count)]
    experiment = client.post('/api/objects', json={'title': f'规模实验{start}', 'kind': 'experiment'}).json()
    for left, right in zip(notes, notes[1:]):
        response = client.post('/api/relations', json={'source_id': left['id'], 'target_id': right['id'], 'relation_type': 'uses',
                                                       'evidence': [{'source_url': 'https://example.com', 'locator': '第1页'}, {'evidence_object_id': left['id']}]})
        assert response.status_code == 201, response.text
    for note in notes:
        client.post('/api/sessions', json={'objective': f'学习{note["title"]}', 'object_ids': [n['id'] for n in notes[:2]]})
        client.post('/api/runs', json={'experiment_id': experiment['id'], 'artifacts': [{'location': 'a.log'}, {'location': 'b.log'}]})
    return notes


def measure(client, statements, canvas_id):
    counts = {}
    for path in ['/api/objects', '/api/relations', '/api/sessions', '/api/runs', '/api/trash', '/api/canvases', f'/api/canvases/{canvas_id}']:
        statements.clear()
        assert client.get(path).status_code == 200, path
        counts[path] = len(statements)
    return counts


def test_list_endpoints_run_a_constant_number_of_queries(client, statements):
    first = populate(client, 4)
    canvas = client.post('/api/canvases', json={'title': '规模画布'}).json()
    items = [{'id': str(uuid4()), 'item_type': 'object', 'object_id': note['id'], 'x': 0, 'y': 0} for note in first]
    relations = client.get('/api/relations').json()
    edges = [{'id': str(uuid4()), 'source_item_id': items[i]['id'], 'target_item_id': items[i + 1]['id'], 'relation_id': relation['id']}
             for i, relation in enumerate(sorted(relations, key=lambda r: r['created_at'])[:3])]
    assert client.put(f"/api/canvases/{canvas['id']}/document", json={'version': 1, 'title': '规模画布', 'items': items, 'edges': edges}).status_code == 200
    small = measure(client, statements, canvas['id'])
    populate(client, 25, start=10)
    large = measure(client, statements, canvas['id'])
    assert small == large, (small, large)
    assert max(small.values()) <= 7      # includes the two lookups the sign-in middleware makes for every request


def test_pagination_headers_order_and_bounds(client):
    notes = populate(client, 25)
    seen = []
    for offset in (0, 10, 20):
        response = client.get(f'/api/objects?limit=10&offset={offset}&q=规模笔记')
        assert response.headers['X-Total-Count'] == '25'
        seen += [item['id'] for item in response.json()]
    assert len(seen) == 25 == len(set(seen)) and set(seen) == {note['id'] for note in notes}
    beyond = client.get('/api/objects?limit=10&offset=500')
    assert beyond.json() == [] and beyond.headers['X-Total-Count'] == '26'
    assert len(client.get('/api/objects?limit=0').json()) == 1 and client.get('/api/objects?offset=-5').status_code == 200
    for path, total in [('/api/relations', 24), ('/api/sessions', 25), ('/api/runs', 25), ('/api/canvases', 0), ('/api/trash', 0)]:
        everything = client.get(path)
        assert everything.headers['X-Total-Count'] == str(total) and len(everything.json()) == total
    page = client.get('/api/relations?limit=5&offset=20')
    assert len(page.json()) == 4 and page.headers['X-Total-Count'] == '24' and all(len(r['evidence']) == 2 for r in page.json())


def test_search_text_is_matched_literally(client):
    percent, underscore, other = (client.post('/api/objects', json={'title': title}).json() for title in ['折扣 100% 优惠', 'a_b 记号', 'axb 记号'])
    assert [o['id'] for o in client.get('/api/objects', params={'q': '%'}).json()] == [percent['id']]
    assert [o['id'] for o in client.get('/api/objects', params={'q': 'a_b'}).json()] == [underscore['id']]
    assert {o['id'] for o in client.get('/api/objects', params={'q': 'x'}).json()} == {other['id']}
    assert client.get('/api/objects', params={'q': '记号'}).headers['X-Total-Count'] == '2'


def reference_neighbourhood(objects, relations, center, depth):
    """Brute force: BFS over relations whose endpoints are both active."""
    active = {o['id'] for o in objects if not o['archived_at']}
    edges = [r for r in relations if r['source_id'] in active and r['target_id'] in active]
    seen, queue = {center}, deque([(center, 0)])
    while queue:
        node, distance = queue.popleft()
        if distance == depth:
            continue
        for edge in edges:
            for here, there in ((edge['source_id'], edge['target_id']), (edge['target_id'], edge['source_id'])):
                if here == node and there not in seen:
                    seen.add(there)
                    queue.append((there, distance + 1))
    nodes = seen & active
    return nodes, {e['id'] for e in edges if e['source_id'] in seen and e['target_id'] in seen}


def test_graph_neighbourhood_matches_a_brute_force_search(client):
    rng = random.Random(7)
    notes = [client.post('/api/objects', json={'title': f'图节点{i}'}).json() for i in range(30)]
    made = 0
    while made < 55:
        a, b = rng.sample(notes, 2)
        if client.post('/api/relations', json={'source_id': a['id'], 'target_id': b['id'], 'relation_type': rng.choice(['depends_on', 'uses', 'supports'])}).status_code == 201:
            made += 1
    for note in notes[:2]:
        assert client.patch(f"/api/objects/{note['id']}", json={**note, 'archived_at': '2026-10-01T00:00:00Z'}).status_code == 200
    for note in notes[2:4]:
        client.delete(f"/api/objects/{note['id']}")
    for relation in client.get('/api/relations').json()[:3]:
        client.delete(f"/api/relations/{relation['id']}")
    objects, relations = client.get('/api/objects?archived=true&limit=1000').json(), client.get('/api/relations').json()
    for center in (notes[5], notes[10], notes[20], notes[0]):
        for depth in (1, 2, 3, 9):
            nodes, edges = reference_neighbourhood(objects, relations, center['id'], min(depth, 3))
            result = client.get(f"/api/graph?center={center['id']}&depth={depth}").json()
            assert {n['id'] for n in result['nodes']} == nodes, (center['title'], depth)
            assert {e['id'] for e in result['edges']} == edges, (center['title'], depth)
    assert client.get(f"/api/graph?center={notes[3]['id']}").json() == {'nodes': [], 'edges': []}
    whole = client.get('/api/graph')
    assert whole.headers['X-Total-Count'] == '26' and len(whole.json()['nodes']) == 26


def test_whole_graph_keeps_the_best_connected_nodes_when_truncated(client):
    hub = client.post('/api/objects', json={'title': '枢纽'}).json()
    leaves = [client.post('/api/objects', json={'title': f'叶子{i}'}).json() for i in range(6)]
    isolated = [client.post('/api/objects', json={'title': f'孤立{i}'}).json() for i in range(8)]
    for leaf in leaves:
        client.post('/api/relations', json={'source_id': hub['id'], 'target_id': leaf['id'], 'relation_type': 'uses'})
    result = client.get('/api/graph?limit=3')
    assert result.headers['X-Total-Count'] == '15'
    titles = {n['title'] for n in result.json()['nodes']}
    assert len(titles) == 3 and '枢纽' in titles and not titles & {n['title'] for n in isolated}
    keep = {n['id'] for n in result.json()['nodes']}
    assert all(e['source_id'] in keep and e['target_id'] in keep for e in result.json()['edges']) and len(result.json()['edges']) == 2


def test_trash_pages_across_all_record_kinds(client):
    a, b = create(client, '回收对象'), create(client, '回收目标')
    relation = client.post('/api/relations', json={'source_id': a['id'], 'target_id': b['id'], 'relation_type': 'uses'}).json()
    canvas = client.post('/api/canvases', json={'title': '回收画布'}).json()
    session = client.post('/api/sessions', json={'objective': '回收学习'}).json()
    experiment = create(client, '回收实验', 'experiment')
    run = client.post('/api/runs', json={'experiment_id': experiment['id'], 'hypothesis_md': '回收假设'}).json()
    plain = client.post('/api/runs', json={'experiment_id': experiment['id']}).json()
    attachment = client.post(f"/api/objects/{b['id']}/attachments", files={'file': ('回收.txt', b'x', 'text/plain')}).json()
    for target in [f"/api/relations/{relation['id']}", f"/api/canvases/{canvas['id']}", f"/api/sessions/{session['id']}", f"/api/runs/{run['id']}",
                   f"/api/runs/{plain['id']}", f"/api/attachments/{attachment['id']}", f"/api/objects/{a['id']}"]:
        assert client.delete(target).status_code == 200, target
    everything = client.get('/api/trash')
    assert everything.headers['X-Total-Count'] == '7'
    rows = everything.json()
    assert [r['kind'] for r in rows] == ['object', 'attachment', 'run', 'run', 'session', 'canvas', 'relation']
    assert [r['title'] for r in rows] == ['回收对象', '回收.txt', '实验运行', '回收假设', '回收学习', '回收画布', '知识关系']
    paged = client.get('/api/trash?limit=3&offset=2').json()
    assert [r['id'] for r in paged] == [r['id'] for r in rows[2:5]]


def test_pool_reuses_connections_and_waits_for_a_free_slot(monkeypatch):
    connection_pool = pool.Pool(DSN, 2)
    first = connection_pool.acquire()
    connection_pool.release(first)
    second = connection_pool.acquire()
    assert second is first
    third = connection_pool.acquire()
    monkeypatch.setattr(pool, 'POOL_WAIT_SECONDS', 0.2)
    with pytest.raises(HTTPException) as error:
        connection_pool.acquire()
    assert error.value.status_code == 503
    connection_pool.release(second)
    connection_pool.release(third, discard=True)
    assert connection_pool.acquire() is second
    connection_pool.close()


def test_pool_drops_connections_that_were_idle_too_long(monkeypatch):
    connection_pool = pool.Pool(DSN, 1)
    first = connection_pool.acquire()
    connection_pool.release(first)
    monkeypatch.setattr(pool, 'IDLE_SECONDS', -1)
    second = connection_pool.acquire()
    assert second is not first and first.closed
    connection_pool.release(second)
    connection_pool.close()


def test_requests_recover_when_pooled_connections_were_killed(client):
    assert client.get('/api/objects').status_code == 200            # puts a connection in the pool
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        # Only this application's connections: background workers such as autovacuum cannot be terminated by an ordinary role.
        cursor.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND application_name=%s', (pool.APPLICATION_NAME,))
    assert client.post('/api/objects', json={'title': '服务重启后'}).status_code == 201
    assert len(client.get('/api/objects').json()) == 1


def test_unreachable_database_is_reported_quickly(client, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://nobody:nothing@127.0.0.1:1/missing')
    assert client.get('/api/health').json()['database'] == 'unavailable'
    assert client.get('/api/objects').status_code == 503
    monkeypatch.delenv('DATABASE_URL')
    assert client.get('/api/objects').status_code == 503


def test_concurrent_requests_share_a_bounded_pool(client):
    from concurrent.futures import ThreadPoolExecutor
    create(client, '并发笔记')
    with ThreadPoolExecutor(max_workers=24) as executor:
        codes = list(executor.map(lambda _: client.get('/api/objects').status_code, range(120)))
    assert set(codes) == {200}
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name=%s", (pool.APPLICATION_NAME,))
        held = cursor.fetchone()[0]
    assert 1 <= held <= pool.POOL_SIZE


def test_search_text_with_a_nul_character_is_ignored_not_a_server_error(client):
    create(client, '含空字符的搜索')
    response = client.get('/api/objects', params={'q': '含空字符\x00的搜索'})
    assert response.status_code == 200 and [item['title'] for item in response.json()] == ['含空字符的搜索']
    assert client.get('/api/objects', params={'kind': 'concept\x00'}).status_code == 200
