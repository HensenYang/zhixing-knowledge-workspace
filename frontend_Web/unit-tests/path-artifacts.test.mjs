import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createPathArtifactHtml, parsePathArtifact, validatePathArtifact, ARTIFACT_MAX_BYTES } from '../src/services/pathArtifacts.js';

const a = '10000000-0000-4000-8000-000000000001';
const b = '10000000-0000-4000-8000-000000000002';
const catalogs = Object.fromEntries(['zh', 'en'].map(language => [language,
  JSON.parse(fs.readFileSync(new URL(`../src/i18n/${language}.json`, import.meta.url), 'utf8'))]));
const example = () => ({ format: 'zhixing-learning-path', version: 1, created_at: '2026-10-22T00:00:00Z', includes_body: true,
  path: { id: a, title: '原始标题 </script><script>bad()</script>', objective_md: 'Understand', description_md: '', completion_criteria_md: 'Explain',
    steps: [a, b].map(id => ({ id, object_id: id, title: '学习步骤', guidance_md: 'Read', completion_criteria_md: 'Explain', estimated_minutes: 5 })) },
  objects: [a, b].map(id => ({ id, kind: 'concept', title: '中文标题', summary: 'Summary', body_md: '<img src=x onerror=bad()>', tags: ['研究'], metadata: { doi: '10.1234/test' }, source_url: 'https://example.org' })),
  relations: [{ id: a, source_id: a, target_id: b, relation_type: 'uses', description: 'Uses', evidence: [] }] });

test('JSON and offline HTML preserve text without letting data close a script tag', () => {
  const value = example();
  const html = createPathArtifactHtml(value, catalogs, 'en');
  assert.deepEqual(parsePathArtifact(JSON.stringify(value)), validatePathArtifact(value));
  assert.deepEqual(parsePathArtifact(html), validatePathArtifact(value));
  const payload = /<script id="zhixing-learning-path" type="application\/json">([\s\S]*?)<\/script>/.exec(html)[1];
  assert.equal(payload.includes('</script>'), false);
  assert.equal(payload.includes('<img'), false);
  assert.ok(html.includes('default-src'));
  assert.ok(html.includes('Learning Path Artifact'));
});

test('untrusted HTML is only parsed for its data payload, never evaluated', () => {
  globalThis.__artifactTest = false;
  const content = `<script>globalThis.__artifactTest=true</script><script id="zhixing-learning-path" type="application/json">${JSON.stringify(example()) .replaceAll('<', '\\u003c')}</script>`;
  assert.equal(parsePathArtifact(content).objects.length, 2);
  assert.equal(globalThis.__artifactTest, false);
  assert.throws(() => parsePathArtifact(content + content), /artifact.invalid/);
});

test('invalid versions, references, unexpected fields and unsafe URLs are rejected', () => {
  const modifications = [value => value.version = 2, value => value.objects.push(value.objects[0]),
    value => value.relations[0].target_id = '20000000-0000-4000-8000-000000000003',
    value => value.objects[0].source_url = 'javascript:alert(1)', value => value.secret = 'private',
    value => value.objects[0].metadata = { api_key: 'private' }, value => value.includes_body = false];
  for (const modify of modifications) { const value = example(); modify(value); assert.throws(() => validatePathArtifact(value), /artifact.invalid/); }
  assert.throws(() => parsePathArtifact('x'.repeat(ARTIFACT_MAX_BYTES + 1)), /artifact.tooLarge/);
});
