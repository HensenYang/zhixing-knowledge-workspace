"""Reachability checks for the external URLs in notes and evidence.

Notes can be imported from anywhere, so a URL in a note must never be able to make this program
probe the local machine or the private network. Every hop is resolved first; if any address is not
a public one the URL is skipped, and the request is sent to the address that was checked (with the
original host name in the Host header and TLS name) so the name cannot resolve differently later.

Results carry a machine-readable `error` code (never a sentence), so the interface can show it in
the user's language: not_found, server_error, restricted, dns_failed, timeout, connect_failed,
too_many_redirects, private_address, unsupported_scheme, check_failed.
"""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit
import ipaddress
import socket

from fastapi import HTTPException
import httpx

import backend.app as workspace

TIMEOUT = 8.0
MAX_REDIRECTS = 5
WORKERS = 8
REVISIT_HOURS = 24
HEAD_REFUSED = {400, 403, 405, 501}
USER_AGENT = 'zhixing-knowledge-workspace link check'


def resolve(host, port):
    return [info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]


def outcome(status_code=None, ok=None, error=None, final_url=None):
    return {'status_code': status_code, 'ok': ok, 'error': error, 'final_url': final_url}


def judge(status, final_url):
    if status < 400:
        return outcome(status, True, None, final_url)
    if status in (404, 410):
        return outcome(status, False, 'not_found', final_url)
    if status >= 500:
        return outcome(status, None, 'server_error', final_url)
    return outcome(status, None, 'restricted', final_url)


def pinned(url, address):
    parts = urlsplit(url)
    host = f'[{address}]' if ':' in address else address
    port = f':{parts.port}' if parts.port else ''
    return parts._replace(netloc=host + port).geturl()


def check_url(url, resolver=resolve, transport=None):
    """Return {'status_code', 'ok', 'error', 'final_url'}; never raises."""
    current = url
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT, follow_redirects=False, headers={'User-Agent': USER_AGENT}) as client:
            for _ in range(MAX_REDIRECTS + 1):
                parts = urlsplit(current)
                if parts.scheme not in ('http', 'https') or not parts.hostname:
                    return outcome(error='unsupported_scheme')
                port = parts.port or (443 if parts.scheme == 'https' else 80)
                try:
                    addresses = resolver(parts.hostname, port)
                except OSError:
                    return outcome(ok=False, error='dns_failed')
                if not addresses or any(not ipaddress.ip_address(address.split('%')[0]).is_global for address in addresses):
                    return outcome(error='private_address')
                target = pinned(current, addresses[0])
                headers = {'Host': parts.netloc.rsplit('@', 1)[-1]}
                extensions = {'sni_hostname': parts.hostname} if parts.scheme == 'https' else {}
                response = client.request('HEAD', target, headers=headers, extensions=extensions)
                if response.status_code in HEAD_REFUSED:
                    with client.stream('GET', target, headers={**headers, 'Range': 'bytes=0-0'}, extensions=extensions) as streamed:
                        status, location = streamed.status_code, streamed.headers.get('location')
                else:
                    status, location = response.status_code, response.headers.get('location')
                if status in (301, 302, 303, 307, 308) and location:
                    current = urljoin(current, location)
                    continue
                return judge(status, current if current != url else None)
            return outcome(ok=False, error='too_many_redirects')
    except httpx.TimeoutException:
        return outcome(ok=False, error='timeout')
    except httpx.HTTPError:
        return outcome(ok=False, error='connect_failed')
    except Exception:   # a bad URL must not stop the whole run
        return outcome(error='check_failed')


USED_URLS = '''SELECT o.source_url AS url FROM objects o
    WHERE o.deleted_at IS NULL AND o.archived_at IS NULL AND o.source_url ~* '^https?://'
    UNION
    SELECT e.source_url FROM relation_evidence e JOIN relations r ON r.id=e.relation_id
    WHERE r.deleted_at IS NULL AND e.source_url ~* '^https?://\''''


def run_link_check(report, force=False):
    """Job body: check every URL in use (in this workspace) that has not been checked recently."""
    with workspace.db() as cursor:
        cursor.execute(f"""SELECT u.url FROM ({USED_URLS}) u LEFT JOIN link_checks c ON c.url=u.url
            WHERE %s OR c.url IS NULL OR c.checked_at < now() - make_interval(hours => %s) ORDER BY u.url LIMIT 5000""", (force, REVISIT_HOURS))
        urls = [row['url'] for row in cursor.fetchall()]
    report(2, f'共 {len(urls)} 个链接待检查')
    results = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for index, (url, result) in enumerate(zip(urls, pool.map(lambda item: check_url(item), urls)), 1):
            results.append((url, result))
            if index % 5 == 0 or index == len(urls):
                report(2 + 96 * index / max(len(urls), 1), f'已检查 {index} / {len(urls)}')
    unreachable = [url for url, result in results if result['ok'] is False and result['status_code'] is None]
    if len(results) >= 5 and len(unreachable) >= 0.8 * len(results):
        raise HTTPException(502, '绝大多数链接都连不上，很可能是本机网络问题；结果没有保存，请联网后重试。')
    with workspace.db() as cursor:
        for url, result in results:
            cursor.execute('''INSERT INTO link_checks(url,status_code,ok,error,final_url,checked_at) VALUES (%s,%s,%s,%s,%s,now())
                ON CONFLICT (url) DO UPDATE SET status_code=EXCLUDED.status_code, ok=EXCLUDED.ok, error=EXCLUDED.error,
                final_url=EXCLUDED.final_url, checked_at=EXCLUDED.checked_at''',
                           (url, result['status_code'], result['ok'], result['error'], result['final_url']))
    return {'checked': len(results), 'dead': sum(1 for _, r in results if r['ok'] is False),
            'unclear': sum(1 for _, r in results if r['ok'] is None), 'reachable': sum(1 for _, r in results if r['ok'])}
