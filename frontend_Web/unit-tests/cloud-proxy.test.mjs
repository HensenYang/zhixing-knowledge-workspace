import {test} from 'node:test';
import assert from 'node:assert/strict';
import {onRequest} from '../functions/api/[[path]].js';

const env={API_ORIGIN:'https://origin.example.test',API_PROXY_SECRET:'server-only-secret-'.repeat(3)};

test('cloud proxy streams uploads, retains workspace/cookies/query and replaces spoofed proxy headers', async t => {
  t.mock.method(globalThis,'fetch', async request => {
    assert.equal(request.url,'https://origin.example.test/api/source-imports/preview-file?name=%E7%A7%91%E5%AD%A6');
    assert.equal(request.method,'POST'); assert.equal(request.headers.get('Cookie'),'knowledge_session=original');
    assert.equal(request.headers.get('X-Workspace-ID'),'workspace-1');
    assert.equal(request.headers.get('X-Zhixing-Proxy-Secret'),env.API_PROXY_SECRET);
    assert.equal(request.headers.get('X-Forwarded-For'),null);
    assert.equal(request.redirect,'manual');
    assert.equal(await request.text(),'original upload bytes');
    return Response.json({ok:true});
  });
  const request=new Request('https://app.example.test/api/source-imports/preview-file?name=%E7%A7%91%E5%AD%A6',{
    method:'POST',body:'original upload bytes',headers:{Cookie:'knowledge_session=original','X-Workspace-ID':'workspace-1',
      'X-Zhixing-Proxy-Secret':'spoofed','X-Forwarded-For':'spoofed'}});
  const result=await onRequest({request,env}); assert.equal(result.status,200); assert.deepEqual(await result.json(),{ok:true});
});

test('cloud proxy preserves secure login/logout cookies, pagination and binary downloads without caching', async t => {
  t.mock.method(globalThis,'fetch',async()=>new Response(new Uint8Array([0,1,2,255]),{status:200,headers:{
    'Content-Type':'application/zip','Content-Disposition':'attachment; filename=backup.zip','X-Total-Count':'123',
    'Set-Cookie':'knowledge_session=value; HttpOnly; Path=/; SameSite=Lax; Secure',
    'Cache-Control':'public, max-age=86400','Cloudflare-CDN-Cache-Control':'max-age=86400'}}));
  const result=await onRequest({request:new Request('https://app.example.test/api/export'),env});
  assert.deepEqual([...new Uint8Array(await result.arrayBuffer())],[0,1,2,255]);
  assert.equal(result.headers.get('Content-Disposition'),'attachment; filename=backup.zip');
  assert.equal(result.headers.get('X-Total-Count'),'123');
  assert.match(result.headers.get('Set-Cookie'),/HttpOnly.*Secure/);
  assert.equal(result.headers.get('Cache-Control'),'private, no-store');
  assert.equal(result.headers.get('Cloudflare-CDN-Cache-Control'),null);
});

test('cloud proxy does not follow redirects with session credentials and rewrites same-origin Location', async t => {
  let calls=0;
  t.mock.method(globalThis,'fetch',async()=>{calls++;return new Response(null,{status:307,headers:{Location:'https://origin.example.test/api/objects/?q=next'}});});
  const result=await onRequest({request:new Request('https://app.example.test/api/objects'),env});
  assert.equal(calls,1); assert.equal(result.status,307);
  assert.equal(result.headers.get('Location'),'https://app.example.test/api/objects/?q=next');
});

test('missing/unsafe configuration and upstream failures return localized errors without secret details', async t => {
  const request=new Request('https://app.example.test/api/health');
  for(const invalid of [{},{...env,API_ORIGIN:'http://origin.example.test'},{...env,API_ORIGIN:'https://user:pass@origin.example.test'},
    {...env,API_ORIGIN:'https://origin.example.test/prefix'},{...env,API_ORIGIN:'https://app.example.test'},{...env,API_PROXY_SECRET:'short'}]) {
    const response=await onRequest({request,env:invalid});
    assert.equal(response.status,503); assert.deepEqual(await response.json(),{detail:'deployment.notConfigured'});
  }
  t.mock.method(globalThis,'fetch',async()=>{throw Error(env.API_PROXY_SECRET);});
  const response=await onRequest({request,env});
  assert.equal(response.status,502); assert.deepEqual(await response.json(),{detail:'deployment.unavailable'});
});

test('upstream authentication failures stay recognizable and encoded paths never change the configured host', async t => {
  t.mock.method(globalThis,'fetch',async request=>{
    assert.equal(new URL(request.url).origin,env.API_ORIGIN);
    assert.equal(new URL(request.url).pathname,'/api/%2F%2Fevil.example/file');
    return Response.json({detail:'请先登录。'},{status:401});
  });
  const response=await onRequest({request:new Request('https://app.example.test/api/%2F%2Fevil.example/file'),env});
  assert.equal(response.status,401); assert.deepEqual(await response.json(),{detail:'请先登录。'});
});
