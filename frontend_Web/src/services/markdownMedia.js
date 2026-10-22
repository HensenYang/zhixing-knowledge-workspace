// Resolve imported resources at render time so existing notes need no rewrite.
export function resolveSourceUrl(value, sourceUrl, metadata = {}, image = false) {
  if (!value || value.startsWith('#') || value.startsWith('//')) return value;
  let source;
  try { source = new URL(sourceUrl); } catch { return value; }
  const match = source.hostname === 'github.com' && /^\/([^/]+)\/([^/]+)(?:\/|$)/.exec(source.pathname);
  if (!match) return value;
  const [, owner, repo] = match;
  if (/^[a-z][a-z0-9+.-]*:/i.test(value)) {
    if (image) {
      try {
        const url = new URL(value);
        if (url.hostname === 'github.com' && /^\/[^/]+\/[^/]+\/blob\//.test(url.pathname)) {
          return 'https://raw.githubusercontent.com' + url.pathname.replace('/blob/', '/') + url.search;
        }
      } catch { /* The renderer's normal URL checks handle malformed input. */ }
    }
    return value;
  }
  // Internal persisted attachments always belong to the workbench.
  if (value.startsWith('/api/')) return value;
  const ref = String(metadata.commit || metadata.default_branch || 'HEAD').split('/').map(encodeURIComponent).join('/');
  const directory = String(metadata.readme_path || 'README.md').split('/').slice(0, -1).map(encodeURIComponent).join('/');
  const base = image ? `https://raw.githubusercontent.com/${owner}/${repo}/${ref}/` : `https://github.com/${owner}/${repo}/blob/${ref}/`;
  try {
    return new URL(value.replace(/^\//, ''), base + (value.startsWith('/') ? '' : directory ? directory + '/' : '')).href;
  } catch { return value; }
}

export function previewAssetMarkdown(body, assets = []) {
  const urls = new Map(assets.map(asset => [asset.id, asset.preview_url]));
  return body.replace(/import-asset:\/\/([a-f0-9-]{36})/g, (original, id) => urls.get(id) || original);
}
