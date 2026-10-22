import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pagesWorkerSource } from '../scripts/package-pages.mjs';
const proxy = await readFile(new URL('../functions/api/[[path]].js', import.meta.url), 'utf8');
const { default: worker } = await import('data:text/javascript;base64,' + Buffer.from(pagesWorkerSource(proxy)).toString('base64'));

test('dashboard upload serves assets through the Pages binding', async () => {
  const request = new Request('https://app.example.com/learning-paths');
  let received;
  const response = await worker.fetch(request, { ASSETS: { fetch(value) { received = value; return new Response('app shell'); } } });
  assert.equal(received, request);
  assert.equal(await response.text(), 'app shell');
});

test('dashboard upload sends API paths through the protected proxy', async () => {
  const response = await worker.fetch(new Request('https://app.example.com/api/health'), {});
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { detail: 'deployment.notConfigured' });
});
