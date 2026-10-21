import { test, expect } from '@playwright/test';

const note = {
  id: 'note-a', title: '保留用户的中文标题', kind: 'model', summary: '用户填写的摘要',
  body_md: '# 用户的原始笔记\n\n公式 $a_t = \\pi(o_t)$', source_url: '',
  reading_status: 'reading', mastery_status: 'unknown', metadata: {}, tags: ['用户标签'], version: 1, archived_at: null
};
const prerequisite = { ...note, id: 'note-b', kind: 'concept', title: '前置知识原文' };
const experiment = { ...note, id: 'experiment-a', kind: 'experiment', title: '用户实验主题' };
const relations = [{ id: 'relation-a', source_id: note.id, target_id: prerequisite.id, relation_type: 'depends_on', description: '' }];
const canvas = { id: 'canvas-a', title: '用户画布标题', version: 1, viewport: { x: 0, y: 0, zoom: 1 }, items: [], edges: [] };

async function mockWorkspace(page, { failSave = false } = {}) {
  const calls = [];
  await page.route('**/api/**', route => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push({ path: url.pathname, method: request.method() });
    let data = [];
    if (url.pathname === '/api/health') data = { service: 'ready', database: 'ready', schema_version: 'V002' };
    else if (url.pathname === '/api/llm/status') data = { configured: false, api_key_configured: false, missing: ['LLM_API_KEY', 'LLM_MODEL'] };
    else if (url.pathname === '/api/learning-paths') data = [];
    else if (url.pathname === '/api/source-imports/providers') data = { providers: ['arxiv', 'doi', 'github', 'pdf'], mcp: { enabled: false } };
    else if (url.pathname === '/api/objects') data = url.searchParams.get('kind') === 'experiment' ? [experiment] : [note, prerequisite, experiment];
    else if (url.pathname === '/api/relations') data = relations;
    else if (url.pathname === '/api/graph') data = { nodes: [note, prerequisite], edges: relations };
    else if (url.pathname === '/api/canvases') data = [canvas];
    else if (url.pathname === '/api/canvases/canvas-a') data = canvas;
    else if (url.pathname === '/api/sessions') data = [{ id: 'session-a', objective: '用户学习记录', occurred_at: '2026-10-20T04:00:00Z', activity_md: '原始学习内容', understanding_change_md: '', blockers_md: '', next_step_md: '', object_ids: [note.id] }];
    else if (url.pathname === '/api/trash') data = [{ id: 'deleted-a', kind: 'object', title: '已删除的用户内容', deleted_at: '2026-10-20T04:00:00Z' }];
    else if (url.pathname === '/api/objects/note-a') {
      if (request.method() === 'PATCH') {
        if (failSave) return route.fulfill({ status: 409, json: { detail: '另一标签页已修改此笔记。草稿已保留，请重新加载后合并。' } });
        data = { ...request.postDataJSON(), id: note.id, version: 2 };
      } else data = note;
    }
    return route.fulfill({ json: data });
  });
  return calls;
}

test('language preference persists across every page and remains reachable on mobile', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const calls = await mockWorkspace(page);
  await page.goto('/');
  await expect(page.locator('h1')).toHaveText('把理解连接起来');
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page).toHaveTitle('Zhixing · Knowledge in Motion');
  await expect(page.locator('h1')).toHaveText('Connect your understanding');
  const routes = [
    ['/knowledge', 'Knowledge & Resources'], ['/imports', 'Source Import'],
    ['/paths', 'Research Learning Paths'], ['/graph', 'Knowledge Graph'],
    ['/canvases', 'Free Canvases'], ['/timeline', 'Learning Journey'],
    ['/experiments', 'Experiments & Reproduction'], ['/trash', 'Recycle Bin'],
    ['/settings', 'Environment & Backup']
  ];
  for (const [route, title] of routes) {
    await page.goto(route);
    await expect(page.locator('h1')).toHaveText(title);
    await expect(page.getByRole('combobox', { name: 'Interface language' })).toHaveValue('en');
  }
  await expect(page.getByRole('region', { name: 'LLM Access' })).toContainText('Configuration incomplete');
  await page.reload();
  await expect(page.getByRole('combobox', { name: 'Interface language' })).toHaveValue('en');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('combobox', { name: 'Interface language' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(calls.some(call => call.method !== 'GET')).toBe(false);
  expect(errors).toEqual([]);
});

test('switching updates graph and dialog labels without translating user content', async ({ page }) => {
  await mockWorkspace(page);
  await page.goto('/knowledge/note-a');
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(page.getByRole('textbox', { name: 'Note title' })).toHaveValue(note.title);
  await expect(page.locator('.markdown')).toContainText('用户的原始笔记');
  const navigation = page.getByRole('region', { name: 'Read through relationships' });
  await expect(navigation).toContainText('Prerequisites / foundations');
  await expect(navigation.getByRole('combobox', { name: 'Reading relationship type' }).locator('option[value="depends_on"]')).toHaveText('Depends on');
  await expect(navigation.locator('.graph-container')).toHaveAttribute('aria-label', /Local graph, current node: 保留用户的中文标题/);
  await navigation.getByRole('button', { name: 'Expand', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Expanded local graph' })).toContainText('Depth 1');
  await page.getByRole('button', { name: 'Close graph' }).click();
  await page.getByRole('button', { name: 'Delete note', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Confirm deletion' })).toContainText(`“${note.title}” will be hidden`);
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh');
  await page.getByRole('button', { name: '删除笔记', exact: true }).click();
  await expect(page.getByRole('dialog', { name: '确认删除' })).toContainText(`「${note.title}」将从当前页面隐藏`);
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await page.goto('/canvases/canvas-a');
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(page.getByRole('button', { name: 'Zoom in', exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Canvas title' })).toHaveValue(canvas.title);
});

test('an unsaved draft and a save conflict survive a language switch', async ({ page }) => {
  const calls = await mockWorkspace(page, { failSave: true });
  await page.goto('/knowledge/note-a?mode=edit');
  const body = page.getByRole('textbox', { name: '笔记正文' });
  const content = '我的未保存草稿 — keep this exactly';
  await body.fill(content);
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(page.getByRole('textbox', { name: 'Note body' })).toHaveValue(content);
  await expect(page.getByRole('alert')).toContainText('Another tab has changed this note. Your draft is retained.');
  await expect(page.locator('.save-status')).toHaveText('Save failed · Draft retained');
  const saves = calls.filter(call => call.method === 'PATCH').length;
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh');
  await expect(page.getByRole('textbox', { name: '笔记正文' })).toHaveValue(content);
  await expect(page.getByRole('alert')).toContainText('另一标签页已修改此笔记');
  await expect(page.locator('.save-status')).toHaveText('保存失败 · 草稿保留');
  expect(calls.filter(call => call.method === 'PATCH')).toHaveLength(saves);
});

test('language changes synchronize other tabs', async ({ page, context }) => {
  await mockWorkspace(page);
  await page.goto('/settings');
  const second = await context.newPage();
  await mockWorkspace(second);
  await second.goto('/settings');
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(second.getByRole('combobox', { name: 'Interface language' })).toHaveValue('en');
  await expect(second.locator('h1')).toHaveText('Environment & Backup');
});

test('import preview keeps edited material and translates source warnings across languages', async ({ page }) => {
  const calls = await mockWorkspace(page);
  await page.route('**/api/source-imports/preview', route => route.fulfill({ json: {
    source_type: 'github', source_key: 'owner/repo', source_url: 'https://github.com/owner/repo',
    title: '用户资料标题', summary: '原始摘要', body_md: '原始正文', suggested_kind: 'repository',
    tags: ['用户标签'], metadata: {}, possible_duplicates: [],
    warnings: ['README 获取失败，已保留仓库元数据。']
  } }));
  await page.goto('/imports');
  await page.getByRole('textbox', { name: '资料地址' }).fill('https://github.com/owner/repo');
  await page.getByRole('button', { name: '提取并预览' }).click();
  await page.getByRole('textbox', { name: '标题', exact: true }).fill('手动编辑的资料标题');
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(page.getByRole('textbox', { name: 'Title', exact: true })).toHaveValue('手动编辑的资料标题');
  await expect(page.getByRole('textbox', { name: 'Markdown body' })).toHaveValue('原始正文');
  await expect(page.locator('.warning-box')).toHaveText('The README could not be fetched. Repository metadata was retained.');
  await expect(page.getByRole('button', { name: 'Confirm and create knowledge object' })).toBeVisible();
  expect(calls.some(call => call.path === '/api/source-imports/commit')).toBe(false);
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh');
  await expect(page.getByRole('textbox', { name: '标题', exact: true })).toHaveValue('手动编辑的资料标题');
  await expect(page.locator('.warning-box')).toHaveText('README 获取失败，已保留仓库元数据。');
});

test('learning path drafts and share pages preserve content when switching language', async ({ page }) => {
  const calls = await mockWorkspace(page);
  const path = { id: 'path-a', title: '用户路径标题', objective_md: '用户学习目标', description_md: '', completion_criteria_md: '', status: 'draft', version: 1, steps: [] };
  await page.route('**/api/learning-paths/path-a', route => route.fulfill({ json: path }));
  await page.goto('/paths/path-a');
  await page.getByRole('button', { name: '独立步骤', exact: true }).click();
  await page.getByRole('textbox', { name: '步骤 1 标题' }).fill('用户未保存的学习步骤');
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(page.getByRole('textbox', { name: 'Step 1 title' })).toHaveValue('用户未保存的学习步骤');
  await expect(page.getByRole('textbox', { name: 'Path title', exact: true })).toHaveValue(path.title);
  await expect(page.getByRole('button', { name: 'Publish and share' })).toBeVisible();
  expect(calls.some(call => call.method === 'PUT')).toBe(false);
  await page.route('**/api/shared/learning-paths/test-token', route => route.fulfill({ json: { ...path, status: 'published' } }));
  await page.goto('/shared/paths/test-token');
  await expect(page.getByRole('heading', { name: 'Learning goal', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: path.title })).toBeVisible();
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh');
  await expect(page.getByRole('heading', { name: '学习目标', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: path.title })).toBeVisible();
});
