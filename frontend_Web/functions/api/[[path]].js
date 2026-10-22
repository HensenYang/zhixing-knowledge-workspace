// Pages keeps browser requests same-origin; the Python API stays on the Ubuntu VM.
const proxyHeader = 'X-Zhixing-Proxy-Secret';
function failure(status, detail) {
  return Response.json({ detail }, { status, headers: { 'Cache-Control': 'no-store' } });
}

export async function onRequest({ request, env }) {
  let origin;
  try {
    origin = new URL(env.API_ORIGIN);
    if (origin.protocol !== 'https:' || origin.username || origin.password || origin.pathname !== '/'
        || origin.search || origin.hash || origin.origin === new URL(request.url).origin
        || typeof env.API_PROXY_SECRET !== 'string' || env.API_PROXY_SECRET.length < 32
        || /[\r\n]/.test(env.API_PROXY_SECRET)) throw Error();
  } catch { return failure(503, 'deployment.notConfigured'); }
  const incoming = new URL(request.url);
  if (!incoming.pathname.startsWith('/api/')) return failure(404, 'deployment.originDenied');
  // Assign pathname, never resolve user-controlled input against the upstream URL.
  origin.pathname = incoming.pathname;
  origin.search = incoming.search;
  const headers = new Headers(request.headers);
  headers.delete('Host');
  headers.delete('Forwarded');
  headers.delete('X-Forwarded-For');
  headers.set('X-Forwarded-Proto', 'https');
  headers.set(proxyHeader, env.API_PROXY_SECRET);
  headers.set('Cache-Control', 'no-store');
  try {
    const upstream = new Request(new Request(origin.toString(), request), { headers, redirect: 'manual' });
    const response = await fetch(upstream, { cf: { cacheEverything: false, cacheTtl: 0 } });
    const outgoing = new Response(response.body, response);
    outgoing.headers.set('Cache-Control', 'private, no-store');
    outgoing.headers.delete('CDN-Cache-Control');
    outgoing.headers.delete('Cloudflare-CDN-Cache-Control');
    outgoing.headers.delete(proxyHeader);
    const location = outgoing.headers.get('Location');
    if (location) {
      const redirected = new URL(location, origin);
      if (redirected.origin === origin.origin) {
        outgoing.headers.set('Location', incoming.origin + redirected.pathname + redirected.search + redirected.hash);
      }
    }
    return outgoing;
  } catch { return failure(502, 'deployment.unavailable'); }
}
