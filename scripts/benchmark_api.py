"""Time the main read endpoints of a running instance.

    python scripts/benchmark_api.py http://127.0.0.1:8001 [--hub <object id>] [--parallel 40]
"""
import argparse
import statistics
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def fetch(base, path):
    started = time.perf_counter()
    with urllib.request.urlopen(base + path, timeout=120) as response:
        body = response.read()
        return time.perf_counter() - started, len(body), response.headers.get('X-Total-Count')


def timed(base, path, repeat):
    results = [fetch(base, path) for _ in range(repeat)]
    return statistics.median(r[0] for r in results) * 1000, results[0][1], results[0][2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('base')
    parser.add_argument('--hub')
    parser.add_argument('--repeat', type=int, default=5)
    parser.add_argument('--parallel', type=int, default=40)
    args = parser.parse_args()
    base = args.base.rstrip('/')
    keyword = urllib.parse.quote('关键词42')
    cases = [('objects (first 200)', '/api/objects?limit=200'), ('objects search "关键词42"', f'/api/objects?q={keyword}&limit=50'),
             ('relations', '/api/relations'), ('sessions', '/api/sessions'), ('runs', '/api/runs'), ('trash', '/api/trash'),
             ('graph, whole', '/api/graph'), ]
    if args.hub:
        cases.append(('graph, hub depth 2', f'/api/graph?center={args.hub}&depth=2'))
    print(f'{"endpoint":<28}{"median ms":>10}{"KB":>9}{"total":>9}')
    for label, path in cases:
        try:
            ms, size, total = timed(base, path, args.repeat)
            print(f'{label:<28}{ms:>10.0f}{size / 1024:>9.0f}{(total or "-"):>9}')
        except Exception as error:
            print(f'{label:<28}{"failed":>10}  {error}')
    started = time.perf_counter()
    with ThreadPoolExecutor(args.parallel) as pool:
        list(pool.map(lambda _: fetch(base, '/api/objects?limit=20'), range(args.parallel * 5)))
    elapsed = time.perf_counter() - started
    print(f'{args.parallel * 5} requests, {args.parallel} in parallel: {args.parallel * 5 / elapsed:.0f} requests/s')


if __name__ == '__main__':
    main()
