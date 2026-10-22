import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createI18n } from '../src/i18n/runtime.js';

const catalogs = Object.fromEntries(['zh', 'en'].map(language => [language,
  JSON.parse(fs.readFileSync(new URL(`../src/i18n/${language}.json`, import.meta.url), 'utf8'))]));

test('uses Chinese by default and restores a supported saved preference', () => {
  assert.equal(createI18n({ catalogs }).getLanguage(), 'zh');
  assert.equal(createI18n({ catalogs, storage: { getItem: () => 'en' } }).t('保存'), 'Save');
  assert.equal(createI18n({ catalogs, storage: { getItem: () => 'invalid' } }).getLanguage(), 'zh');
});

test('switching persists and notifies without storing or changing any workspace content', () => {
  const writes = [];
  let notifications = 0;
  const store = createI18n({ catalogs, storage: { setItem: (...args) => writes.push(args) } });
  const unsubscribe = store.subscribe(() => notifications++);
  store.setLanguage('en');
  assert.equal(store.t('知识与资料'), 'Knowledge & Resources');
  assert.deepEqual(writes, [['workspace:language', 'en']]);
  assert.equal(notifications, 1);
  store.setLanguage('en');
  assert.equal(notifications, 1);
  unsubscribe();
  store.setLanguage('zh', { persist: false });
  assert.equal(store.t('保存'), '保存');
  assert.equal(notifications, 1);
  assert.equal(writes.length, 2);
});

test('storage failures do not prevent in-memory switching', () => {
  const store = createI18n({ catalogs, storage: {
    getItem() { throw Error('blocked'); }, setItem() { throw Error('blocked'); }
  } });
  store.setLanguage('en');
  assert.equal(store.t('保存'), 'Save');
  store.setLanguage('fr');
  assert.equal(store.getLanguage(), 'en');
});

test('placeholders preserve user text including dollar signs and braces', () => {
  const store = createI18n({ catalogs });
  const title = '我的笔记 $& {example}';
  store.setLanguage('en');
  assert.equal(store.t('永久删除「{title}」？', { title }), `Permanently delete “${title}”?`);
  assert.equal(title, '我的笔记 $& {example}');
});

test('stored message keys and parameterized server errors translate at render time', () => {
  const store = createI18n({ catalogs });
  const status = store.msg('保存失败 · 草稿保留');
  const error = store.msg('{key} 必须是文本。', { key: 'doi' });
  store.setLanguage('en');
  assert.equal(store.t(status), 'Save failed · Draft retained');
  assert.equal(store.translateMessage(error), 'doi must be text.');
  assert.equal(store.translateMessage('LLM 尚未配置，请在后端 .env 设置：LLM_MODEL，然后重启后端。'),
    'The LLM is not configured. Set LLM_MODEL in the backend .env file, then restart the backend.');
  assert.equal(store.translateMessage('Request timeout'), 'Request timeout');
  store.setLanguage('zh');
  assert.equal(store.translateMessage(error), 'doi 必须是文本。');
});
