"""Fill a scratch schema of the TEST database with synthetic data, to measure behaviour at scale.

    DATABASE_URL=<test database url> python scripts/seed_scale_data.py --schema bench --objects 5000

Never point this at your real database: the schema is dropped and recreated.
"""
import argparse
import os
from pathlib import Path
import random
import re
import uuid

import psycopg2
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parents[1]
KINDS = ['concept', 'resource', 'repository', 'model', 'dataset', 'benchmark', 'question', 'task']
TOPICS = ['扩散模型', '流匹配', '世界模型', '动作表示', '视觉语言', '强化学习', '模仿学习', '机器人操作', '数据集', '评测基准']
LINKS = ['depends_on', 'uses', 'supports', 'implements', 'evaluates', 'questions']


def build_schema(cursor, schema, through):
    cursor.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
    for path in sorted((ROOT / 'database/migrations').glob('V*.sql')):
        if path.name.split('__')[0] <= through:
            cursor.execute(path.read_text(encoding='utf-8').replace('knowledge.', f'{schema}.').replace('CREATE SCHEMA knowledge;', f'CREATE SCHEMA {schema};'))


def fill(cursor, count, seed):
    rng = random.Random(seed)
    ids = [str(uuid.UUID(int=rng.getrandbits(128), version=4)) for _ in range(count)]
    tags = {name: str(uuid.UUID(int=rng.getrandbits(128), version=4)) for name in [f'标签{i}' for i in range(40)]}
    execute_values(cursor, 'INSERT INTO tags(id,name) VALUES %s', list(map(lambda item: (item[1], item[0]), tags.items())))
    rows = []
    for index, identifier in enumerate(ids):
        topic = rng.choice(TOPICS)
        body = (f'# {topic} {index}\n\n' + f'{topic}相关的学习笔记，记录输入、输出与训练目标。 ' * 12 + f'\n\n关键词{index % 97} 与 {rng.choice(TOPICS)}。')
        rows.append((identifier, rng.choice(KINDS), f'基准笔记 {index:05d} {topic}', f'{topic}摘要', body, f'https://example.com/{index}', Json({})))
    execute_values(cursor, 'INSERT INTO objects(id,kind,title,summary,body_md,source_url,metadata) VALUES %s', rows, page_size=1000)
    names = list(tags)
    execute_values(cursor, 'INSERT INTO object_tags(object_id,tag_id) VALUES %s',
                   [(identifier, tags[name]) for identifier in ids for name in rng.sample(names, 3)], page_size=2000)
    seen, relations, evidence = set(), [], []
    hubs = ids[:20]
    while len(relations) < count * 3:
        source = rng.choice(hubs) if rng.random() < 0.15 else rng.choice(ids)
        target = rng.choice(ids)
        kind = rng.choice(LINKS)
        if source == target or (source, target, kind) in seen:
            continue
        seen.add((source, target, kind))
        relation = str(uuid.UUID(int=rng.getrandbits(128), version=4))
        relations.append((relation, source, target, kind, ''))
        if rng.random() < 0.6:
            evidence.append((str(uuid.UUID(int=rng.getrandbits(128), version=4)), relation, None, 'https://example.com/e', '第3页', ''))
    execute_values(cursor, 'INSERT INTO relations(id,source_id,target_id,relation_type,description) VALUES %s', relations, page_size=2000)
    execute_values(cursor, 'INSERT INTO relation_evidence(id,relation_id,evidence_object_id,source_url,locator,explanation) VALUES %s', evidence, page_size=2000)
    sessions = [(str(uuid.UUID(int=rng.getrandbits(128), version=4)), f'学习记录{i}') for i in range(count // 10)]
    execute_values(cursor, 'INSERT INTO learning_sessions(id,objective) VALUES %s', sessions)
    execute_values(cursor, 'INSERT INTO session_objects(session_id,object_id) VALUES %s', [(s[0], identifier) for s in sessions for identifier in rng.sample(ids, 2)])
    experiments = ids[-(count // 50 or 1):]
    cursor.execute("UPDATE objects SET kind='experiment' WHERE id = ANY(%s::uuid[])", (experiments,))
    runs = [(str(uuid.UUID(int=rng.getrandbits(128), version=4)), rng.choice(experiments)) for _ in range(count // 10)]
    execute_values(cursor, 'INSERT INTO experiment_runs(id,experiment_id) VALUES %s', runs)
    execute_values(cursor, 'INSERT INTO run_artifacts(run_id,artifact_type,location) VALUES %s', [(run[0], 'file', f'run-{i}.log') for i, run in enumerate(runs) for _ in range(2)])
    cursor.execute('ANALYZE')
    return ids, hubs[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--schema', required=True)
    parser.add_argument('--objects', type=int, default=5000)
    parser.add_argument('--through', default='V999', help='apply migrations up to this version, e.g. V002 for the pre-index schema')
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', args.schema) or args.schema == 'knowledge':
        raise SystemExit('Use a scratch schema name (not "knowledge").')
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise SystemExit('Set DATABASE_URL to the TEST database.')
    with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
        build_schema(cursor, args.schema, args.through)
        cursor.execute(f'SET search_path TO {args.schema}, public')
        ids, hub = fill(cursor, args.objects, args.seed)
    print(f'{args.schema}: {args.objects} notes, {args.objects * 3} relations; busiest hub {hub}')


if __name__ == '__main__':
    main()
