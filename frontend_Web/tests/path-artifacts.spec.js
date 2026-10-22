import { test, expect } from '@playwright/test';

const pathId = '10000000-0000-4000-8000-000000000001';
const a = '20000000-0000-4000-8000-000000000001';
const b = '20000000-0000-4000-8000-000000000002';
const importedId = '30000000-0000-4000-8000-000000000001';
const fixture = (body = false) => ({
  format: 'zhixing-learning-path', version: 1, created_at: '2026-10-22T00:00:00Z', includes_body: body,
  path: { id: pathId, title: '从论文到可验证实验', objective_md: '解释方法与证据', description_md: '保留原始中文内容', completion_criteria_md: '独立解释数据流',
    steps: [a, b].map((id, index) => ({ id, object_id: id, title: index ? '验证方法' : '理解基础', guidance_md: '阅读原始来源', completion_criteria_md: '解释并给出依据', estimated_minutes: 10 })) },
  objects: [a, b].map((id, index) => ({ id, kind: index ? 'resource' : 'concept', title: index ? '原始论文' : '世界模型', summary: '用户的关键摘要',
    body_md: body ? '原始正文 <img src=x onerror="window.__artifactXss=true">' : '', source_url: 'https://example.org/paper', tags: ['研究'], metadata: { doi: '10.1234/test' } })),
  relations: [{ id: pathId, source_id: a, target_id: b, relation_type: 'uses', description: '方法与论文的关系', evidence: [{ evidence_object_id: b, source_url: 'https://example.org/paper', locator: '第 3 页', explanation: '证据说明' }] }]
});

async function mockWorkspace(page, { signedIn = true, role = 'owner' } = {}) {
  let doc = { ...fixture().path, status: 'draft', share_token: null, version: 1 };
  const calls = [], imports = [];
  await page.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url());
    calls.push({ path: url.pathname, query: url.search, method: request.method() });
    let data = [];
    if (url.pathname === '/api/auth/me') {
      if (!signedIn) return route.fulfill({ status: 401, json: { detail: '请先登录。' } });
      data = { id: a, email: 'owner@example.test', display_name: 'Owner', workspaces: [{ id: b, name: 'Test workspace', role }] };
    } else if (url.pathname === '/api/health') data = { service: 'ready', database: 'ready' };
    else if (url.pathname === '/api/objects') data = fixture().objects;
    else if (url.pathname.endsWith('/artifact')) data = fixture(url.searchParams.get('include_body') === 'true');
    else if (url.pathname === '/api/learning-paths/import') {
      const body = request.postDataBuffer().toString('utf8');
      imports.push(JSON.parse(/\r\n\r\n([\s\S]*?)\r\n--/.exec(body)[1]));
      doc = { ...fixture().path, id: importedId, status: 'draft', share_token: null, version: 1 };
      return route.fulfill({ status: 201, json: doc });
    } else if (url.pathname.startsWith('/api/shared/learning-paths/')) data = { ...doc, artifact: fixture() };
    else if (url.pathname.startsWith('/api/learning-paths/')) {
      if (request.method() === 'PUT') doc = { ...doc, ...request.postDataJSON(), version: doc.version + 1 };
      data = doc;
    }
    return route.fulfill({ json: data });
  });
  return { calls, imports };
}
async function downloadedText(download) {
  const chunks = [];
  for await (const chunk of await download.createReadStream()) chunks.push(chunk);
  return Buffer.concat(chunks).toString('utf8');
}

test('saved path exports an offline interactive artifact and a portable JSON snapshot', async ({ page, browser }) => {
  const { calls } = await mockWorkspace(page);
  await page.goto(`/paths/${pathId}`);
  await page.getByRole('button', { name: '保存并预览 Artifact', exact: true }).click();
  await expect(page.locator('.artifact-node')).toHaveCount(2);
  await expect(page.locator('.artifact-inspector')).toContainText('第 3 页');
  expect(calls.findIndex(call => call.method === 'PUT')).toBeLessThan(calls.findIndex(call => call.path.endsWith('/artifact')));
  const jsonDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 JSON 文件包', exact: true }).click();
  const json = JSON.parse(await downloadedText(await jsonDownload));
  expect(json.includes_body).toBe(false);
  expect(json.objects.every(object => object.body_md === '')).toBe(true);
  const htmlDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载离线 HTML Artifact', exact: true }).click();
  const html = await downloadedText(await htmlDownload);
  const offline = await browser.newContext({ offline: true });
  try {
    const view = await offline.newPage();
    const errors = [];
    view.on('pageerror', error => errors.push(error.message));
    await view.setContent(html);
    await expect(view.getByRole('heading', { name: fixture().path.title, exact: true })).toBeVisible();
    await view.getByRole('button', { name: '原始论文', exact: true }).click();
    await expect(view.locator('.artifact-inspector h3').first()).toHaveText('原始论文');
    await view.getByRole('combobox', { name: '展示语言' }).selectOption('en');
    await expect(view.getByRole('heading', { name: 'Key information and evidence' })).toBeVisible();
    await expect(view.locator('.artifact-inspector h3').first()).toHaveText('原始论文');
    expect(errors).toEqual([]);
  } finally { await offline.close(); }
});

test('HTML file preview never executes embedded code and saving is explicit', async ({ page }) => {
  const { imports } = await mockWorkspace(page);
  await page.goto('/artifacts');
  const value = fixture(true);
  const payload = JSON.stringify(value).replaceAll('<', '\\u003c');
  const file = `<script>window.__artifactXss=true</script><script id="zhixing-learning-path" type="application/json">${payload}</script>`;
  await page.getByLabel('选择 HTML 或 JSON 学习路径文件').setInputFiles({ name: 'shared.html', mimeType: 'text/html', buffer: Buffer.from(file) });
  await expect(page.locator('.artifact-node')).toHaveCount(2);
  await expect(page.getByRole('heading', { name: value.path.title, exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.__artifactXss)).toBeUndefined();
  expect(imports).toHaveLength(0);
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await page.getByRole('button', { name: 'Save a copy to this workspace', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/paths/${importedId}$`));
  expect(imports).toHaveLength(1);
  expect(imports[0].objects[0].body_md).toBe(value.objects[0].body_md);
  expect(imports[0].relations[0].evidence[0].locator).toBe('第 3 页');
});

test('anonymous visitors can browse files and published graphs but cannot save', async ({ page }) => {
  await mockWorkspace(page, { signedIn: false });
  await page.goto('/artifacts');
  await page.getByLabel('选择 HTML 或 JSON 学习路径文件').setInputFiles({ name: 'path.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(fixture())) });
  await expect(page.locator('.artifact-node')).toHaveCount(2);
  await expect(page.getByRole('button', { name: '保存副本到当前工作区', exact: true })).toBeDisabled();
  await page.goto('/shared/paths/example_public_token');
  await expect(page.locator('.artifact-node')).toHaveCount(2);
  await expect(page.getByRole('button', { name: '下载 JSON 文件包', exact: true })).toBeVisible();
});

test('invalid files clear the old preview, and viewer roles cannot import copies', async ({ page }) => {
  await mockWorkspace(page, { role: 'viewer' });
  await page.goto('/artifacts');
  const input = page.getByLabel('选择 HTML 或 JSON 学习路径文件');
  await input.setInputFiles({ name: 'good.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(fixture())) });
  await expect(page.locator('.artifact-node')).toHaveCount(2);
  await expect(page.getByRole('button', { name: '保存副本到当前工作区', exact: true })).toBeDisabled();
  await input.setInputFiles({ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('{"version":99}') });
  await expect(page.getByRole('alert')).toContainText('学习路径文件无效');
  await expect(page.locator('.artifact-node')).toHaveCount(0);
});
