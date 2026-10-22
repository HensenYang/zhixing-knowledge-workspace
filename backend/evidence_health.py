"""Evidence health: where the knowledge base claims more than it can show.

Every check reads only active records (not deleted, not archived), through the same row-level
security as every other request, so a workspace only ever sees its own data. Checks that can be
expressed as a query are counted and paged in the database; the two that need code (dated sources,
dependency cycles) are computed in Python. Nothing here changes data.

A finding carries a `code` and `params` for the interface to render in the user's language; `message`
is the same sentence in Chinese for API consumers and logs.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Response

import backend.app as workspace
from backend import jobs, link_checker
from backend.paging import page, set_total

router = APIRouter(prefix='/api/evidence-health')
SEVERITIES = ('error', 'warning', 'info')
RELATION_LABELS = {'depends_on': '依赖', 'implements': '实现', 'uses': '使用', 'evaluates': '评测', 'supports': '支持',
                   'questions': '质疑', 'compares_with': '比较', 'related_to': '相关'}
EXTERNAL_KINDS = ('resource', 'repository', 'model', 'dataset', 'benchmark')
RUN_FIELDS = {'command': '运行命令', 'git_commit': '代码提交（commit）', 'config': '配置', 'metrics': '指标', 'failure_md': '失败原因'}
LINK_ERRORS = {'not_found': '页面不存在', 'server_error': '服务端暂时错误', 'restricted': '需要登录或被限制', 'dns_failed': '域名无法解析', 'timeout': '连接超时',
               'connect_failed': '无法连接', 'too_many_redirects': '重定向次数过多', 'private_address': '本机或内网地址，未检查',
               'unsupported_scheme': '不是 http(s) 地址', 'check_failed': '无法检查'}
MASTERY_CLAIMS = {'implement': '能实现', 'reproduce': '能复现'}
MESSAGES = {
    'relation_no_evidence': '《{source}》{relation}《{target}》：没有任何证据。',
    'evidence_object_deleted': '《{source}》{relation}《{target}》：证据笔记《{evidence}》已被删除。',
    'evidence_bad_url': '《{source}》{relation}《{target}》：来源地址不是 http(s) 链接：{url}。',
    'evidence_no_locator': '《{source}》{relation}《{target}》：有证据，但没有页码、章节或行号。',
    'link_dead': '{url} 打不开（{error}），被{where}使用。',
    'claim_experiment_unverified': '实验《{experiment}》声称{relation}《{target}》，但没有一次成功的运行记录。',
    'claim_mastery_unverified': '《{title}》的理解程度标为“{claim}”，但没有关联的成功实验运行。',
    'run_incomplete': '实验《{experiment}》有一次{status}的运行缺少：{missing}。',
    'source_stale': '《{title}》上次核对于 {verified_on}，已过去 {age_days} 天（超过 {stale_days} 天）。',
    'source_undated': '《{title}》没有记录核对日期（verified_on），无法判断来源是否仍然有效。',
    'dependency_cycle': '“依赖”关系成环：{path}。',
    'contested': '《{title}》被 {supporters} 个来源支持，也被 {questioners} 个来源质疑。',
}
ACTIVE = '''relations r JOIN objects a ON a.id=r.source_id JOIN objects b ON b.id=r.target_id
    WHERE r.deleted_at IS NULL AND a.deleted_at IS NULL AND b.deleted_at IS NULL AND a.archived_at IS NULL AND b.archived_at IS NULL'''
RELATION_COLUMNS = '''r.id::text AS relation_id, r.relation_type, r.description,
    a.id::text AS source_id, a.title AS source_title, a.kind AS source_kind,
    b.id::text AS target_id, b.title AS target_title, b.kind AS target_kind'''


@dataclass(frozen=True)
class Check:
    id: str
    severity: str          # the worst severity a finding of this check can have
    title: str
    description: str
    fix: str


CHECKS = [
    Check('invalid_evidence', 'error', '证据本身有问题', '证据指向已删除的笔记，或来源地址不是 http(s) 链接。', '改成有效的来源地址，或恢复被删除的证据笔记。'),
    Check('dead_links', 'error', '失效链接', '笔记来源或证据里的链接已经打不开（404、域名无法解析、连接失败）。需要先点“检查链接”。', '换成新的地址，或用存档链接代替。'),
    Check('relations_without_evidence', 'warning', '关系没有证据', '这条关系没有任何证据：没有来源链接，也没有指向支撑它的笔记。', '打开关系，补一条证据：来源地址或证据笔记，并写明页码／章节。'),
    Check('unverified_experiment_claims', 'warning', '尚未验证的实验声明', '实验声称支持、质疑或评测了某个对象，却没有成功的运行记录；或理解程度标成“能实现／能复现”，却没有关联的成功实验。', '在“实验与复现”里补上运行并记录结果，或把声明改回“待验证”。'),
    Check('incomplete_runs', 'warning', '无法复现的运行记录', '成功的运行缺少命令、代码提交、配置或指标；失败的运行没有写失败原因。', '补全这些字段，别人才能重复这次运行。'),
    Check('stale_sources', 'warning', '资料可能已过期', '资料的核对日期早于设定天数（警告），或没有记录核对日期（提示）。', '重新核对来源，并在扩展属性里更新 verified_on（YYYY-MM-DD）。'),
    Check('dependency_cycles', 'warning', '依赖关系成环', '“依赖”关系形成了环：A 依赖 B、B 又依赖 A。前置知识不能循环。', '检查环中哪一条依赖方向有误，改成“相关”或删除。'),
    Check('evidence_without_locator', 'info', '证据没有定位', '关系有证据，但都没有写页码、章节或行号，读者很难回到原文。', '给证据补上定位（如“第 3 节”“p.12”）。'),
    Check('contested_claims', 'info', '被支持也被质疑的结论', '同一个对象既有“支持”它的关系，也有“质疑”它的关系。这不一定是错误，但需要人工判断。', '比较双方证据，必要时在笔记里写下你的结论与理由。'),
]
CHECKS_BY_ID = {check.id: check for check in CHECKS}


def zh_message(code, params):
    """The Chinese sentence for a finding. Parameters hold identifiers; this turns them into words."""
    words = dict(params)
    if 'relation' in words:
        words['relation'] = RELATION_LABELS.get(words['relation'], words['relation'])
    if 'claim' in words:
        words['claim'] = MASTERY_CLAIMS[words['claim']]
    if 'error' in words:
        words['error'] = LINK_ERRORS.get(words['error'], words['error'])
        parts = []
        if words.get('objects'):
            parts.append(f'{words["objects"]} 篇笔记的来源')
        if words.get('evidence'):
            parts.append(f'{words["evidence"]} 条证据')
        words['where'] = '、'.join(parts)
    if 'missing' in words:
        words['missing'] = '、'.join(RUN_FIELDS[name] for name in params['missing'])
    if 'status' in words:
        words['status'] = '成功' if params['status'] == 'succeeded' else '失败'
    return MESSAGES[code].format(**words)


def node(row, prefix):
    return {'id': row[f'{prefix}_id'], 'title': row[f'{prefix}_title'], 'kind': row[f'{prefix}_kind']}


def relation_ref(row):
    return {'id': row['relation_id'], 'relation_type': row['relation_type'], 'source': node(row, 'source'), 'target': node(row, 'target')}


def relation_params(row, **extra):
    return {'source': row['source_title'], 'relation': row['relation_type'], 'target': row['target_title'], **extra}


def finding(check, key, code, params, severity=None, objects=(), relation=None, detail=None):
    return {'check': check, 'key': f'{check}:{key}', 'severity': severity or CHECKS_BY_ID[check].severity, 'code': code, 'params': params,
            'message': zh_message(code, params), 'objects': list(objects), 'relation': relation, 'detail': detail or {}}


# ----------------------------------------------------------------- checks that are a query

def q_without_evidence(**_):
    return (f'SELECT {RELATION_COLUMNS} FROM {ACTIVE} AND NOT EXISTS (SELECT 1 FROM relation_evidence e WHERE e.relation_id=r.id)',
            (), 'source_title, target_title, relation_id',
            lambda row: finding('relations_without_evidence', row['relation_id'], 'relation_no_evidence', relation_params(row), relation=relation_ref(row)))


def q_invalid_evidence(**_):
    sql = f'''SELECT e.id::text AS evidence_id, e.source_url, eo.title AS evidence_title, eo.id::text AS evidence_object_id,
        CASE WHEN eo.deleted_at IS NOT NULL THEN 'object_deleted' ELSE 'bad_url' END AS reason, {RELATION_COLUMNS}
        FROM relation_evidence e JOIN relations r ON r.id=e.relation_id JOIN objects a ON a.id=r.source_id JOIN objects b ON b.id=r.target_id
        LEFT JOIN objects eo ON eo.id=e.evidence_object_id
        WHERE r.deleted_at IS NULL AND a.deleted_at IS NULL AND b.deleted_at IS NULL AND a.archived_at IS NULL AND b.archived_at IS NULL
        AND (eo.deleted_at IS NOT NULL OR (e.source_url IS NOT NULL AND e.source_url !~* '^https?://'))'''

    def build(row):
        if row['reason'] == 'object_deleted':
            code, params = 'evidence_object_deleted', relation_params(row, evidence=row['evidence_title'])
        else:
            code, params = 'evidence_bad_url', relation_params(row, url=row['source_url'])
        return finding('invalid_evidence', row['evidence_id'], code, params, relation=relation_ref(row), detail={'reason': row['reason']})
    return sql, (), 'source_title, target_title, evidence_id', build


def q_without_locator(**_):
    return (f'''SELECT {RELATION_COLUMNS} FROM {ACTIVE} AND EXISTS (SELECT 1 FROM relation_evidence e WHERE e.relation_id=r.id)
        AND NOT EXISTS (SELECT 1 FROM relation_evidence e WHERE e.relation_id=r.id AND btrim(e.locator) <> '')''',
            (), 'source_title, target_title, relation_id',
            lambda row: finding('evidence_without_locator', row['relation_id'], 'evidence_no_locator', relation_params(row), relation=relation_ref(row)))


def q_dead_links(**_):
    sql = '''WITH used AS (
            SELECT o.source_url AS url, o.id::text AS object_id, o.title AS object_title, NULL::text AS relation_id FROM objects o
            WHERE o.deleted_at IS NULL AND o.archived_at IS NULL AND o.source_url ~* '^https?://'
            UNION ALL
            SELECT e.source_url, NULL, NULL, r.id::text FROM relation_evidence e JOIN relations r ON r.id=e.relation_id
            WHERE r.deleted_at IS NULL AND e.source_url ~* '^https?://')
        SELECT c.url, c.status_code, c.error, c.checked_at,
            COALESCE(jsonb_agg(DISTINCT jsonb_build_object('id', u.object_id, 'title', u.object_title)) FILTER (WHERE u.object_id IS NOT NULL), '[]'::jsonb) AS objects,
            count(*) FILTER (WHERE u.relation_id IS NOT NULL) AS evidence_uses
        FROM used u JOIN link_checks c ON c.url=u.url WHERE c.ok IS FALSE GROUP BY c.url, c.status_code, c.error, c.checked_at'''

    def build(row):
        params = {'url': row['url'], 'error': row['error'], 'status': row['status_code'], 'objects': len(row['objects']), 'evidence': row['evidence_uses']}
        return finding('dead_links', row['url'], 'link_dead', params, objects=[{**item, 'kind': None} for item in row['objects']],
                       detail={'url': row['url'], 'status_code': row['status_code'], 'checked_at': row['checked_at']})
    return sql, (), 'url', build


def q_unverified_claims(**_):
    sql = f'''SELECT 'experiment_without_success' AS reason, NULL::text AS mastery_status, {RELATION_COLUMNS} FROM {ACTIVE}
        AND a.kind='experiment' AND r.relation_type IN ('supports','questions','evaluates')
        AND NOT EXISTS (SELECT 1 FROM experiment_runs u WHERE u.experiment_id=a.id AND u.status='succeeded' AND u.deleted_at IS NULL)
        UNION ALL
        SELECT 'mastery_without_run', o.mastery_status, NULL, NULL, NULL, o.id::text, o.title, o.kind, NULL, NULL, NULL
        FROM objects o WHERE o.deleted_at IS NULL AND o.archived_at IS NULL AND o.mastery_status IN ('implement','reproduce')
        AND NOT EXISTS (SELECT 1 FROM relations r JOIN objects x ON x.kind='experiment' AND x.deleted_at IS NULL
            AND ((x.id=r.source_id AND r.target_id=o.id) OR (x.id=r.target_id AND r.source_id=o.id))
            JOIN experiment_runs u ON u.experiment_id=x.id AND u.status='succeeded' AND u.deleted_at IS NULL WHERE r.deleted_at IS NULL)'''

    def build(row):
        if row['reason'] == 'mastery_without_run':
            return finding('unverified_experiment_claims', f'mastery:{row["source_id"]}', 'claim_mastery_unverified',
                           {'title': row['source_title'], 'claim': row['mastery_status']}, objects=[node(row, 'source')], detail={'reason': row['reason']})
        return finding('unverified_experiment_claims', row['relation_id'], 'claim_experiment_unverified',
                       {'experiment': row['source_title'], 'relation': row['relation_type'], 'target': row['target_title']},
                       relation=relation_ref(row), detail={'reason': row['reason']})
    return sql, (), 'reason DESC, source_title, relation_id', build


def q_incomplete_runs(**_):
    sql = '''SELECT * FROM (SELECT u.id::text AS run_id, u.status, x.id::text AS experiment_id, x.title AS experiment_title,
        array_remove(ARRAY[
            CASE WHEN u.status='succeeded' AND btrim(u.command)='' THEN 'command' END,
            CASE WHEN u.status='succeeded' AND btrim(COALESCE(u.git_commit,''))='' THEN 'git_commit' END,
            CASE WHEN u.status='succeeded' AND u.config='{}'::jsonb THEN 'config' END,
            CASE WHEN u.status='succeeded' AND u.metrics='{}'::jsonb THEN 'metrics' END,
            CASE WHEN u.status='failed' AND btrim(u.failure_md)='' THEN 'failure_md' END], NULL) AS missing
        FROM experiment_runs u JOIN objects x ON x.id=u.experiment_id WHERE u.deleted_at IS NULL AND x.deleted_at IS NULL) runs WHERE cardinality(missing) > 0'''

    def build(row):
        return finding('incomplete_runs', row['run_id'], 'run_incomplete', {'experiment': row['experiment_title'], 'status': row['status'], 'missing': row['missing']},
                       objects=[{'id': row['experiment_id'], 'title': row['experiment_title'], 'kind': 'experiment'}], detail={'run_id': row['run_id'], 'missing': row['missing']})
    return sql, (), 'experiment_title, run_id', build


def q_contested(**_):
    def side(kind):
        return f"""jsonb_agg(jsonb_build_object('id', a.id::text, 'title', a.title) ORDER BY a.title) FILTER (WHERE r.relation_type='{kind}')"""
    sql = f'''SELECT b.id::text AS target_id, b.title AS target_title, b.kind AS target_kind, {side('supports')} AS supporters, {side('questions')} AS questioners
        FROM {ACTIVE} AND r.relation_type IN ('supports','questions') GROUP BY b.id, b.title, b.kind
        HAVING count(*) FILTER (WHERE r.relation_type='supports') > 0 AND count(*) FILTER (WHERE r.relation_type='questions') > 0'''

    def build(row):
        return finding('contested_claims', row['target_id'], 'contested', {'title': row['target_title'], 'supporters': len(row['supporters']), 'questioners': len(row['questioners'])},
                       objects=[node(row, 'target')], detail={'supporters': row['supporters'], 'questioners': row['questioners']})
    return sql, (), 'target_title', build


QUERY_CHECKS = {'relations_without_evidence': q_without_evidence, 'invalid_evidence': q_invalid_evidence, 'evidence_without_locator': q_without_locator,
                'dead_links': q_dead_links, 'unverified_experiment_claims': q_unverified_claims, 'incomplete_runs': q_incomplete_runs, 'contested_claims': q_contested}


# ----------------------------------------------------------------- checks that need code

def strongly_connected(edges):
    """Tarjan's algorithm, iterative. Returns the components with more than one node."""
    graph = {}
    for source, target in edges:
        graph.setdefault(source, []).append(target)
        graph.setdefault(target, [])
    index, low, on_stack, stack, found, counter = {}, {}, set(), [], [], 0
    for start in graph:
        if start in index:
            continue
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        work = [(start, iter(graph[start]))]
        while work:
            current, successors = work[-1]
            descended = False
            for following in successors:
                if following not in index:
                    index[following] = low[following] = counter
                    counter += 1
                    stack.append(following)
                    on_stack.add(following)
                    work.append((following, iter(graph[following])))
                    descended = True
                    break
                if following in on_stack:
                    low[current] = min(low[current], index[following])
            if descended:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[current])
            if low[current] == index[current]:
                members = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    members.append(member)
                    if member == current:
                        break
                if len(members) > 1:
                    found.append(members)
    return found


def cycle_through(start, members, edges):
    """One concrete cycle inside a component, as an ordered list starting at `start`."""
    allowed = set(members)
    successors = {}
    for source, target in edges:
        if source in allowed and target in allowed:
            successors.setdefault(source, []).append(target)
    queue, parent = [start], {start: None}
    for node_id in queue:
        for following in successors.get(node_id, []):
            if following == start:
                path = [node_id]
                while parent[path[-1]] is not None:
                    path.append(parent[path[-1]])
                return path[::-1]
            if following not in parent:
                parent[following] = node_id
                queue.append(following)
    return sorted(members)


def load_cycles(cursor, **_):
    cursor.execute(f"SELECT a.id::text AS source_id, b.id::text AS target_id, a.title AS source_title, b.title AS target_title FROM {ACTIVE} AND r.relation_type='depends_on'")
    rows = cursor.fetchall()
    titles = {}
    for row in rows:
        titles[row['source_id']], titles[row['target_id']] = row['source_title'], row['target_title']
    edges = [(row['source_id'], row['target_id']) for row in rows]
    result = []
    for members in strongly_connected(edges):
        start = min(members, key=lambda item: titles[item])
        order = cycle_through(start, members, edges)
        path = ' → '.join([titles[item] for item in order] + [titles[order[0]]])
        result.append(finding('dependency_cycles', '|'.join(sorted(members)), 'dependency_cycle', {'path': path},
                              objects=[{'id': item, 'title': titles[item], 'kind': None} for item in order], detail={'size': len(members)}))
    return sorted(result, key=lambda item: item['params']['path'])


def load_stale(cursor, stale_days=180, today=None, **_):
    today = today or date.today()
    cursor.execute('''SELECT id::text AS id, title, kind, source_url, metadata->>'verified_on' AS verified_on FROM objects
        WHERE deleted_at IS NULL AND archived_at IS NULL AND kind = ANY(%s) AND source_url IS NOT NULL AND source_url <> '' ''', (list(EXTERNAL_KINDS),))
    result = []
    for row in cursor.fetchall():
        try:
            verified = date.fromisoformat(row['verified_on']) if row['verified_on'] else None
        except ValueError:
            verified = None
        target = [{'id': row['id'], 'title': row['title'], 'kind': row['kind']}]
        if verified is None:
            result.append(finding('stale_sources', row['id'], 'source_undated', {'title': row['title']}, severity='info', objects=target,
                                  detail={'verified_on': None, 'age_days': None}))
        elif (today - verified).days > stale_days:
            age = (today - verified).days
            result.append(finding('stale_sources', row['id'], 'source_stale', {'title': row['title'], 'verified_on': verified.isoformat(), 'age_days': age, 'stale_days': stale_days},
                                  objects=target, detail={'verified_on': verified.isoformat(), 'age_days': age}))
    return sorted(result, key=lambda item: (item['severity'] != 'warning', -(item['detail']['age_days'] or 0), item['key']))


CODE_CHECKS = {'dependency_cycles': load_cycles, 'stale_sources': load_stale}


# ----------------------------------------------------------------- queries behind the API

def count_findings(cursor, check_id, **options):
    if check_id in CODE_CHECKS:
        items = CODE_CHECKS[check_id](cursor, **options)
        counts = {}
        for item in items:
            counts[item['severity']] = counts.get(item['severity'], 0) + 1
        return len(items), counts
    sql, params, _, _ = QUERY_CHECKS[check_id](**options)
    cursor.execute(f'SELECT count(*) AS total FROM ({sql}) q', params)
    total = cursor.fetchone()['total']
    return total, ({CHECKS_BY_ID[check_id].severity: total} if total else {})


def page_findings(cursor, check_id, limit, offset, **options):
    if check_id in CODE_CHECKS:
        return CODE_CHECKS[check_id](cursor, **options)[offset:offset + limit]
    sql, params, order, build = QUERY_CHECKS[check_id](**options)
    cursor.execute(f'SELECT * FROM ({sql}) q ORDER BY {order} LIMIT %s OFFSET %s', (*params, limit, offset))
    return [build(row) for row in cursor.fetchall()]


def coverage(cursor):
    cursor.execute(f'''SELECT count(*) AS total, count(*) FILTER (WHERE EXISTS (SELECT 1 FROM relation_evidence e WHERE e.relation_id=r.id)) AS with_evidence,
        count(*) FILTER (WHERE EXISTS (SELECT 1 FROM relation_evidence e WHERE e.relation_id=r.id AND btrim(e.locator) <> '')) AS with_locator FROM {ACTIVE}''')
    row = cursor.fetchone()
    total = row['total']
    return {'relations': total, 'with_evidence': row['with_evidence'], 'with_locator': row['with_locator'],
            'percent': round(100 * row['with_evidence'] / total, 1) if total else None}


def link_summary(cursor):
    cursor.execute('''WITH used AS (
            SELECT source_url AS url FROM objects WHERE deleted_at IS NULL AND archived_at IS NULL AND source_url ~* '^https?://'
            UNION SELECT e.source_url FROM relation_evidence e JOIN relations r ON r.id=e.relation_id WHERE r.deleted_at IS NULL AND e.source_url ~* '^https?://')
        SELECT count(*) AS distinct_urls, count(c.url) AS checked, count(*) FILTER (WHERE c.ok IS FALSE) AS dead,
               count(*) FILTER (WHERE c.url IS NOT NULL AND c.ok IS NULL) AS unclear, max(c.checked_at) AS last_checked_at
        FROM used u LEFT JOIN link_checks c ON c.url=u.url''')
    return cursor.fetchone()


def options(stale_days):
    return {'stale_days': min(max(stale_days, 1), 3650)}


@router.get('')
def summary(stale_days: int = 180):
    """Counts for every check, evidence coverage and the state of the link check."""
    settings = options(stale_days)
    with workspace.db() as cursor:
        checks, totals = [], dict.fromkeys(SEVERITIES, 0)
        for check in CHECKS:
            count, by_severity = count_findings(cursor, check.id, **settings)
            for severity, number in by_severity.items():
                totals[severity] += number
            checks.append({'id': check.id, 'severity': check.severity, 'title': check.title, 'description': check.description, 'fix': check.fix,
                           'count': count, 'by_severity': by_severity})
        return {'generated_at': datetime.now(timezone.utc), 'stale_days': settings['stale_days'], 'coverage': coverage(cursor),
                'links': link_summary(cursor), 'totals': totals, 'checks': checks}


@router.get('/{check_id}')
def findings(check_id: str, response: Response, stale_days: int = 180, limit: int = 50, offset: int = 0):
    if check_id not in CHECKS_BY_ID:
        raise HTTPException(404, '没有这项检查。')
    limit, offset = page(limit, offset, 200)
    settings = options(stale_days)
    with workspace.db() as cursor:
        total, _ = count_findings(cursor, check_id, **settings)
        set_total(response, total)
        return {'check': {'id': check_id, 'title': CHECKS_BY_ID[check_id].title, 'description': CHECKS_BY_ID[check_id].description, 'fix': CHECKS_BY_ID[check_id].fix},
                'total': total, 'findings': page_findings(cursor, check_id, limit, offset, **settings)}


@router.post('/link-check', status_code=202)
def start_link_check(response: Response, force: bool = False):
    """Check the external links in the background. A run that is already queued or running is reused."""
    with workspace.db() as cursor:
        cursor.execute("SELECT id FROM background_jobs WHERE kind='link_check' AND status IN ('queued','running') ORDER BY created_at DESC LIMIT 1")
        running = cursor.fetchone()
    if running:
        response.status_code = 200
        return {'job_id': str(running['id']), 'status': 'running', 'already_running': True}
    return {'job_id': jobs.submit('link_check', lambda report: link_checker.run_link_check(report, force=force)), 'status': 'queued', 'already_running': False}
