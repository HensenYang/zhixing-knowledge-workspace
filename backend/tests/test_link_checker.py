"""The link checker must never be a way to probe the local machine or the private network."""
import httpx
import pytest

from backend import link_checker


def public(host, port):
    return {'example.com': ['93.184.216.34'], 'other.example': ['93.184.216.35']}.get(host) or (_ for _ in ()).throw(OSError('no such host'))


def check(url, handler, resolver=public):
    return link_checker.check_url(url, resolver=resolver, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize('address', ['127.0.0.1', '10.0.0.5', '192.168.1.20', '172.16.0.9', '169.254.169.254', '100.64.0.1', '::1', 'fe80::1', '0.0.0.0'])
def test_non_public_addresses_are_never_contacted(address):
    def handler(request):
        raise AssertionError(f'must not send a request to {request.url}')
    result = check('http://internal.example/admin', handler, resolver=lambda host, port: [address])
    assert result['ok'] is None and result['error'] == 'private_address'


def test_a_name_that_resolves_to_both_public_and_private_addresses_is_skipped():
    result = check('http://mixed.example/', lambda request: pytest.fail('no request expected'), resolver=lambda host, port: ['93.184.216.34', '10.0.0.1'])
    assert result['ok'] is None and result['error'] == 'private_address'


def test_only_http_urls_are_checked_and_names_must_resolve():
    for url in ['ftp://example.com/x', 'file:///etc/passwd', 'javascript:alert(1)', 'http:///nohost']:
        result = check(url, lambda request: pytest.fail('no request expected'))
        assert result['ok'] is None and result['error'] == 'unsupported_scheme'
    assert check('http://unknown.example/', lambda request: pytest.fail('no request expected')) == {'status_code': None, 'ok': False, 'error': 'dns_failed', 'final_url': None}


def test_the_request_goes_to_the_address_that_was_checked():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200)
    result = check('https://example.com/paper?id=1', handler)
    request = seen[0]
    assert result['ok'] is True and request.method == 'HEAD'
    assert request.url.host == '93.184.216.34' and request.url.path == '/paper' and request.url.query == b'id=1'
    assert request.headers['host'] == 'example.com' and request.extensions['sni_hostname'] == 'example.com'


def test_head_refused_falls_back_to_a_one_byte_range_request():
    methods = []

    def handler(request):
        methods.append((request.method, request.headers.get('range')))
        return httpx.Response(405 if request.method == 'HEAD' else 206)
    assert check('http://example.com/', handler)['ok'] is True
    assert methods == [('HEAD', None), ('GET', 'bytes=0-0')]


@pytest.mark.parametrize('status,ok,code', [(200, True, None), (301, True, None), (404, False, 'not_found'), (410, False, 'not_found'), (401, None, 'restricted'),
                                            (403, None, 'restricted'), (429, None, 'restricted'), (500, None, 'server_error'), (503, None, 'server_error')])
def test_status_codes_are_judged_carefully(status, ok, code):
    result = check('http://example.com/', lambda request: httpx.Response(status))
    assert (result['ok'], result['error'], result['status_code']) == (ok, code, status)


def test_redirects_are_followed_and_every_hop_is_checked():
    def handler(request):
        if request.headers['host'] == 'example.com':
            return httpx.Response(301, headers={'location': 'https://other.example/new'})
        return httpx.Response(200)
    result = check('http://example.com/old', handler)
    assert result['ok'] is True and result['final_url'] == 'https://other.example/new'

    def to_internal(request):
        return httpx.Response(302, headers={'location': 'http://internal.example/secret'})
    skipped = check('http://example.com/', to_internal, resolver=lambda host, port: ['10.0.0.1'] if host == 'internal.example' else ['93.184.216.34'])
    assert skipped['ok'] is None and skipped['error'] == 'private_address'

    loop = check('http://example.com/', lambda request: httpx.Response(302, headers={'location': '/again'}))
    assert loop['ok'] is False and loop['error'] == 'too_many_redirects'
    assert check('http://example.com/', lambda request: httpx.Response(302, headers={'location': 'ftp://example.com/x'}))['error'] == 'unsupported_scheme'


def test_network_failures_are_reported_not_raised():
    def refuse(request):
        raise httpx.ConnectError('refused')

    def slow(request):
        raise httpx.ConnectTimeout('slow')
    assert check('http://example.com/', refuse) == {'status_code': None, 'ok': False, 'error': 'connect_failed', 'final_url': None}
    assert check('http://example.com/', slow)['error'] == 'timeout'
