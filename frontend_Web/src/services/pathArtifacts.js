import { mountPathArtifact, ARTIFACT_STYLES } from '../artifacts/viewer.js';

export const ARTIFACT_MAX_BYTES = 8 * 1024 * 1024;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const kinds = new Set(['concept', 'resource', 'repository', 'model', 'dataset', 'benchmark', 'experiment', 'question', 'task']);
const relationTypes = new Set(['depends_on', 'implements', 'uses', 'evaluates', 'supports', 'questions', 'compares_with', 'related_to']);
const metadataKeys = new Set(['subtype', 'doi', 'arxiv', 'authors', 'year', 'commit', 'weight_version', 'dataset_version', 'inputs', 'outputs']);
function fail(key = 'artifact.invalid') { throw new Error(key); }
function object(value, fields) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !fields.includes(key))) fail();
}
function text(value, max, required = false) {
  if (typeof value !== 'string' || value.length > max || (required && !value.trim())) fail();
}
function id(value) { if (typeof value !== 'string' || !uuid.test(value)) fail(); }
function url(value) {
  if (value == null || value === '') return;
  text(value, 4000);
  try { const parsed = new URL(value); if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) fail(); }
  catch { fail(); }
}
function list(value, limit) { if (!Array.isArray(value) || value.length > limit) fail(); }
function unique(rows) { if (new Set(rows.map(row => row.id)).size !== rows.length) fail(); }

export function validatePathArtifact(input) {
  const artifact = structuredClone(input);
  object(artifact, ['format', 'version', 'created_at', 'includes_body', 'path', 'objects', 'relations']);
  if (artifact.format !== 'zhixing-learning-path' || artifact.version !== 1 || typeof artifact.includes_body !== 'boolean'
      || typeof artifact.created_at !== 'string' || !Number.isFinite(Date.parse(artifact.created_at))) fail();
  object(artifact.path, ['id', 'title', 'objective_md', 'description_md', 'completion_criteria_md', 'steps']);
  id(artifact.path.id); text(artifact.path.title, 500, true);
  for (const field of ['objective_md', 'description_md', 'completion_criteria_md']) text(artifact.path[field], 200000);
  list(artifact.path.steps, 100); list(artifact.objects, 100); list(artifact.relations, 1000);
  for (const step of artifact.path.steps) {
    object(step, ['id', 'object_id', 'title', 'guidance_md', 'completion_criteria_md', 'estimated_minutes']);
    id(step.id); if (step.object_id != null) id(step.object_id);
    text(step.title, 500, true); text(step.guidance_md, 200000); text(step.completion_criteria_md, 200000);
    if (step.estimated_minutes != null && (!Number.isInteger(step.estimated_minutes) || step.estimated_minutes < 0 || step.estimated_minutes > 100000)) fail();
  }
  for (const item of artifact.objects) {
    object(item, ['id', 'kind', 'title', 'summary', 'body_md', 'source_url', 'tags', 'metadata']);
    id(item.id); if (!kinds.has(item.kind)) fail(); text(item.title, 500, true);
    text(item.summary, 50000); text(item.body_md, 1000000); url(item.source_url);
    list(item.tags, 100); item.tags.forEach(tag => text(tag, 200));
    item.metadata ??= {};
    object(item.metadata, [...metadataKeys]);
    for (const value of Object.values(item.metadata)) {
      if (typeof value === 'string') text(value, 10000);
      else if (Array.isArray(value)) { list(value, 100); value.forEach(entry => text(entry, 1000)); }
      else if (!Number.isSafeInteger(value)) fail();
    }
    if (!artifact.includes_body && item.body_md) fail();
  }
  unique(artifact.path.steps); unique(artifact.objects); unique(artifact.relations);
  const ids = new Set(artifact.objects.map(item => item.id));
  const selected = new Set(artifact.path.steps.map(step => step.object_id).filter(Boolean));
  if (selected.size !== ids.size || [...selected].some(identifier => !ids.has(identifier))) fail();
  const edges = new Set();
  for (const edge of artifact.relations) {
    object(edge, ['id', 'source_id', 'target_id', 'relation_type', 'description', 'evidence']);
    id(edge.id); if (!ids.has(edge.source_id) || !ids.has(edge.target_id) || edge.source_id === edge.target_id || !relationTypes.has(edge.relation_type)) fail();
    text(edge.description, 50000); list(edge.evidence, 100);
    const ends = [edge.source_id, edge.target_id];
    if (['related_to', 'compares_with'].includes(edge.relation_type)) ends.sort();
    const key = [...ends, edge.relation_type].join(':'); if (edges.has(key)) fail(); edges.add(key);
    for (const evidence of edge.evidence) {
      object(evidence, ['evidence_object_id', 'source_url', 'locator', 'explanation']);
      if (evidence.evidence_object_id != null && !ids.has(evidence.evidence_object_id)) fail();
      url(evidence.source_url); text(evidence.locator, 10000); text(evidence.explanation, 50000);
      if (!evidence.evidence_object_id && !evidence.source_url) fail();
    }
  }
  if (new TextEncoder().encode(JSON.stringify(artifact)).length > ARTIFACT_MAX_BYTES) fail('artifact.tooLarge');
  return artifact;
}

export function parsePathArtifact(content) {
  if (new TextEncoder().encode(content).length > ARTIFACT_MAX_BYTES) fail('artifact.tooLarge');
  try {
    let text = content.replace(/^\uFEFF/, '').trim();
    if (!text.startsWith('{')) {
      const payloads = [];
      // Extract data only. Uploaded HTML is never mounted, opened, or executed.
      for (const match of text.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
        const attrs = Object.fromEntries([...match[1].matchAll(/\b(id|type)\s*=\s*["']([^"']*)["']/gi)].map(attr => [attr[1].toLowerCase(), attr[2]]));
        if (attrs.id === 'zhixing-learning-path' && attrs.type === 'application/json') payloads.push(match[2]);
      }
      if (payloads.length !== 1) fail();
      text = payloads[0];
    }
    return validatePathArtifact(JSON.parse(text));
  } catch (error) { if (error.message === 'artifact.tooLarge') throw error; fail(); }
}

const scriptJson = value => JSON.stringify(value).replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
export function createPathArtifactHtml(input, catalogs, language = 'zh') {
  const artifact = validatePathArtifact(input);
  const messages = Object.fromEntries(['zh', 'en'].map(locale => [locale,
    Object.fromEntries(Object.entries(catalogs[locale]).filter(([key]) => key.startsWith('artifact.')))]));
  const title = catalogs[language === 'en' ? 'en' : 'zh']['artifact.badge'].replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const html = '<!doctype html>\n<html lang="' + (language === 'en' ? 'en' : 'zh-CN') + '"><head><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
    + '<title>' + title + '</title><style>body{margin:0;padding:24px;background:#f5f6f1}' + ARTIFACT_STYLES + '</style></head><body>'
    + '<main id="artifact-root"></main><script id="zhixing-learning-path" type="application/json">' + scriptJson(artifact) + '</script>'
    + '<script>const artifact=JSON.parse(document.getElementById("zhixing-learning-path").textContent);('
    + mountPathArtifact.toString() + ')(document.getElementById("artifact-root"),artifact,' + scriptJson(messages) + ',' + scriptJson(language) + ');</script></body></html>';
  if (new TextEncoder().encode(html).length > ARTIFACT_MAX_BYTES) fail('artifact.tooLarge');
  return html;
}

export function downloadArtifact(artifact, format, catalogs, language) {
  const content = format === 'html' ? createPathArtifactHtml(artifact, catalogs, language) : JSON.stringify(validatePathArtifact(artifact), null, 2);
  if (new TextEncoder().encode(content).length > ARTIFACT_MAX_BYTES) fail('artifact.tooLarge');
  const blob = new Blob([content], { type: format === 'html' ? 'text/html;charset=utf-8' : 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url;
  link.download = `learning-path-${artifact.path.id}.${format}`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
