import { readFile, writeFile, access } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export function pagesWorkerSource(proxySource) {
  return proxySource + `
// Pages advanced mode keeps the same proxy for dashboard uploads.
export default {
  fetch(request, env) {
    if (new URL(request.url).pathname.startsWith('/api/')) {
      return onRequest({ request, env });
    }
    return env.ASSETS.fetch(request);
  },
};
`;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  await access(resolve(root, 'dist/index.html'));
  const proxy = await readFile(resolve(root, 'functions/api/[[path]].js'), 'utf8');
  await writeFile(resolve(root, 'dist/_worker.js'), pagesWorkerSource(proxy));
  console.log('Pages dashboard upload prepared in dist, including the API proxy.');
}
