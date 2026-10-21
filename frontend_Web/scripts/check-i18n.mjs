import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from '@babel/parser';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const catalogs = Object.fromEntries(['zh', 'en'].map(language => [language,
  JSON.parse(fs.readFileSync(path.join(root, 'src/i18n', language + '.json'), 'utf8'))]));
const errors = [];
const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort().join(',');
for (const key of new Set([...Object.keys(catalogs.zh), ...Object.keys(catalogs.en)])) {
  for (const language of ['zh', 'en']) {
    if (typeof catalogs[language][key] !== 'string' || !catalogs[language][key].trim()) errors.push(`${language}: missing ${key}`);
  }
  if (catalogs.zh[key] && catalogs.en[key] && placeholders(catalogs.zh[key]) !== placeholders(catalogs.en[key])) {
    errors.push(`Placeholder mismatch: ${key}`);
  }
  if (!['中文', 'artifact.chinese'].includes(key) && /[\u3400-\u9fff]/.test(catalogs.en[key] || '')) errors.push(`Untranslated English entry: ${key}`);
}

const technicalText = new Set(['PostgreSQL', 'API Key', 'commit:', 'KB', 'https://…']);
const uiAttributes = new Set(['title', 'label', 'placeholder', 'aria-label', 'eyebrow']);
function check(node, ancestors, file) {
  if (!node || typeof node !== 'object') return;
  const parent = ancestors.at(-1);
  const location = `${file}:${node.loc?.start.line || 1}`;
  const messageCall = node.type === 'CallExpression' && ['t', 'msg', 'tr'].includes(node.callee?.name);
  if (messageCall && node.arguments[0]?.type === 'StringLiteral') {
    const key = node.arguments[0].value;
    if (!Object.hasOwn(catalogs.zh, key) || !Object.hasOwn(catalogs.en, key)) errors.push(`${location}: unknown message ${key}`);
  }
  if (node.type === 'JSXText') {
    const text = node.value.trim();
    if (/[A-Za-z\u3400-\u9fff]/.test(text) && !technicalText.has(text)) errors.push(`${location}: wrap visible text in t(): ${text}`);
  }
  if (node.type === 'JSXAttribute' && uiAttributes.has(node.name.name) && node.value?.type === 'StringLiteral'
      && !technicalText.has(node.value.value) && /[A-Za-z\u3400-\u9fff]/.test(node.value.value)) {
    errors.push(`${location}: translate the ${node.name.name} attribute`);
  }
  if (node.type === 'StringLiteral' && /[\u3400-\u9fff]/.test(node.value)) {
    const marked = parent?.type === 'CallExpression' && ['t', 'msg', 'tr'].includes(parent.callee?.name) && parent.arguments[0] === node;
    if (!marked) errors.push(`${location}: unmarked Chinese string ${node.value}`);
  }
  if (node.type === 'TemplateLiteral' && node.quasis.some(part => /[\u3400-\u9fff]/.test(part.value.cooked || ''))) {
    errors.push(`${location}: use a catalog message with placeholders`);
  }
  if (node.type === 'CallExpression' && node.callee?.type === 'MemberExpression'
      && ['prompt', 'alert', 'confirm'].includes(node.callee.property?.name) && node.arguments[0]?.type === 'StringLiteral') {
    errors.push(`${location}: translate browser dialog text`);
  }
  for (const [key, value] of Object.entries(node)) {
    if (['loc', 'start', 'end', 'extra', 'comments', 'leadingComments', 'trailingComments', 'innerComments', 'tokens'].includes(key)) continue;
    if (Array.isArray(value)) value.forEach(child => check(child, [...ancestors, node], file));
    else if (value?.type) check(value, [...ancestors, node], file);
  }
}
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) { if (entry.name !== 'i18n') walk(file); }
    else if (/\.(jsx|js)$/.test(file)) check(parse(fs.readFileSync(file, 'utf8'), { sourceType: 'module', plugins: ['jsx'] }), [], path.relative(root, file));
  }
}
walk(path.join(root, 'src'));
if (errors.length) { console.error(errors.join('\n')); process.exitCode = 1; }
else console.log(`i18n checks passed: ${Object.keys(catalogs.zh).length} paired messages; no unmarked interface text.`);
