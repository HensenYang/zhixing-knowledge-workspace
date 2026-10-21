import { test, expect } from '@playwright/test';
const authenticatedUser = {"id":"40000000-0000-4000-8000-000000000001","email":"test@example.test","display_name":"Test user","workspaces":[{"id":"40000000-0000-4000-8000-000000000002","name":"Test workspace","role":"owner"}]};

test('LLM import follows document language and preserves original images until explicit confirmation', async({page})=>{
  const calls=[];
  const raw='## Original English paper\n\nOriginal method and findings.\n\n![Figure](import-asset://11111111-1111-4111-8111-111111111111)';
  await page.route('**/api/**',route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(path==='/api/auth/me') return route.fulfill({json:authenticatedUser});
    calls.push({path,body:request.method()==='POST'?request.postDataJSON():null});
    const data=path.endsWith('/health')?{database:'ready'}:path.endsWith('/providers')?{mcp:{enabled:false}}:
      path.endsWith('/preview')?{source_type:'mcp',source_key:'zotero:local:0:ABCD1234',title:'English paper',summary:'Original abstract',body_md:raw,suggested_kind:'resource',metadata:{import_provider:'zotero'},assets:[],preview_token:'a'.repeat(32)}:
      path.endsWith('/analyze')?{language:'en',summary:'English findings',analysis_md:'## Methods\nEvidence-based English analysis.',provenance:{language:'en',model:'test',excerpted:true}}:
      path.endsWith('/commit')?{id:'analyzed-note'}:[];
    return route.fulfill({json:data});
  });
  await page.goto('/imports');
  await page.getByLabel('资料地址',{exact:true}).fill('10.1234/paper');
  await page.getByRole('button',{name:'提取并预览',exact:true}).click();
  await page.getByRole('button',{name:'使用 LLM 解析',exact:true}).click();
  const body=page.getByRole('textbox',{name:'Markdown 正文',exact:true});
  await expect(body).toHaveValue(`## Methods\nEvidence-based English analysis.\n\n---\n\n${raw}`);
  await expect(page.getByRole('textbox',{name:'摘要',exact:true})).toHaveValue('English findings');
  expect(calls.filter(c=>c.path.endsWith('/commit'))).toHaveLength(0);
  expect(calls.find(c=>c.path.endsWith('/analyze')).body.body_md).toBe(raw);
  await page.getByRole('combobox',{name:'界面语言'}).selectOption('en');
  await expect(page.getByRole('textbox',{name:'Summary',exact:true})).toHaveValue('English findings');
  await expect(page.getByText('This text is long.',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Confirm and create knowledge object',exact:true}).click();
  await expect(page.getByRole('link',{name:'Open imported material'})).toBeVisible();
  const saved=calls.find(c=>c.path.endsWith('/commit')).body;
  expect(saved.object.body_md).toContain(raw);
  expect(saved.preview_token).toBe('a'.repeat(32));
  expect(saved.object.metadata.llm_analysis.language).toBe('en');
});

test('a duplicate conflict links to the existing import and allows explicit separate-note saving',async({page})=>{
  let commits=0,payload;
  await page.route('**/api/**',route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(path==='/api/auth/me') return route.fulfill({json:authenticatedUser});
    if(path.endsWith('/commit')){
      commits++;payload=request.postDataJSON();
      if(commits===1)return route.fulfill({status:409,json:{detail:{message:'该来源已经导入，请打开已有资料或选择另存笔记。',existing_import:{id:'existing-note',title:'Existing original',deleted_at:null}}}});
      return route.fulfill({status:201,json:{id:'separate-note'}});
    }
    return route.fulfill({json:path.endsWith('/health')?{database:'ready'}:path.endsWith('/providers')?{mcp:{enabled:false}}:path.endsWith('/preview')?{source_type:'mcp',source_key:'zotero:local:0:ABCD1234',title:'Draft paper',summary:'',body_md:'Preserved draft',suggested_kind:'resource',metadata:{},assets:[]}:[]});
  });
  await page.goto('/imports');
  await page.getByLabel('资料地址',{exact:true}).fill('10.1234/paper');
  await page.getByRole('button',{name:'提取并预览',exact:true}).click();
  await page.getByRole('button',{name:'确认并创建知识对象',exact:true}).click();
  await expect(page.getByRole('link',{name:'Existing original'})).toHaveAttribute('href','/knowledge/existing-note');
  await expect(page.getByRole('button',{name:'确认并创建知识对象',exact:true})).toBeDisabled();
  await page.getByRole('combobox',{name:'界面语言'}).selectOption('en');
  await expect(page.getByText('This source is already imported. Open the existing material or save a separate note.',{exact:true})).toBeVisible();
  await expect(page.getByRole('textbox',{name:'Markdown body',exact:true})).toHaveValue('Preserved draft');
  await page.getByRole('checkbox',{name:'Save as a separate note',exact:false}).check();
  await page.getByRole('button',{name:'Confirm and save separate note'}).click();
  await expect(page.getByRole('link',{name:'Open imported material'})).toHaveAttribute('href','/knowledge/separate-note');
  expect(payload.save_as_note).toBe(true);
});

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
    if (url.pathname === '/api/auth/me') data = authenticatedUser;
    else if (url.pathname === '/api/health') data = { service: 'ready', database: 'ready', schema_version: 'V002' };
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

test('Zotero search and preview preserve original material across languages and only import after confirmation', async ({ page }) => {
  await mockWorkspace(page);
  const calls = [];
  const preview = {
    source_type: 'mcp', source_key: 'zotero:local:0:ABCD1234', source_url: 'https://example.org/paper',
    title: '本机 Zotero 文献原题', summary: '原始摘要', body_md: '## Document Content\n原始全文内容',
    suggested_kind: 'resource', tags: ['用户标签'], metadata: { import_provider: 'zotero', zotero_item_key: 'ABCD1234', fulltext_included: true },
    warnings: [], possible_duplicates: []
  };
  await page.route('**/api/source-imports/**', route => {
    const request = route.request(), url = new URL(request.url());
    const payload = request.method() === 'POST' ? request.postDataJSON() : null;
    calls.push({ path: url.pathname, payload });
    const data = url.pathname.endsWith('/providers') ? { zotero: { enabled: true, configured: true }, mcp: { enabled: false } }
      : url.pathname.endsWith('/zotero/search') ? { items: [{ item_key: 'ABCD1234', title: preview.title, authors: 'Wang, A', date: '2026' }] }
      : url.pathname.endsWith('/zotero/preview') ? preview : { id: 'imported-zotero' };
    return route.fulfill({ json: data });
  });
  await page.goto('/imports');
  await page.getByLabel('来源类型').selectOption('zotero');
  await expect(page.getByRole('button', { name: '搜索 Zotero 文献' })).toBeDisabled();
  await page.getByRole('textbox', { name: 'Zotero 搜索词' }).fill('用户搜索词');
  await page.getByLabel('搜索范围', { exact: true }).selectOption('everything');
  await page.getByLabel('筛选标签（可选）').fill('用户标签');
  await page.getByRole('button', { name: '搜索 Zotero 文献' }).click();
  await expect(page.locator('.zotero-results')).toContainText(preview.title);
  expect(calls.filter(call => call.path.endsWith('/zotero/preview'))).toHaveLength(0);
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(page.getByRole('textbox', { name: 'Zotero search query' })).toHaveValue('用户搜索词');
  await expect(page.getByLabel('Tag filter (optional)')).toHaveValue('用户标签');
  await expect(page.getByLabel('Search scope', { exact: true })).toHaveValue('everything');
  await page.getByRole('button', { name: `Preview item: ${preview.title}` }).click();
  await expect(page.getByRole('textbox', { name: 'Markdown body' })).toHaveValue(preview.body_md);
  await page.getByRole('textbox', { name: 'Title', exact: true }).fill('手动编辑的文献标题');
  expect(calls.some(call => call.path.endsWith('/commit'))).toBe(false);
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh');
  await expect(page.getByRole('textbox', { name: '标题', exact: true })).toHaveValue('手动编辑的文献标题');
  await expect(page.getByRole('textbox', { name: 'Markdown 正文' })).toHaveValue(preview.body_md);
  await page.getByRole('button', { name: '确认并创建知识对象' }).click();
  await expect(page.getByRole('link', { name: '打开已导入资料' })).toHaveAttribute('href', '/knowledge/imported-zotero');
  const confirmation = calls.find(call => call.path.endsWith('/commit')).payload;
  expect(confirmation.source_type).toBe('mcp');
  expect(confirmation.source_key).toBe(preview.source_key);
  expect(confirmation.object.title).toBe('手动编辑的文献标题');
  expect(confirmation.object.body_md).toBe(preview.body_md);
  expect(calls.find(call => call.path.endsWith('/zotero/search')).payload).toMatchObject({ query: '用户搜索词', qmode: 'everything', tag: '用户标签' });
});

test('Zotero search errors, empty results, metadata-only mode and full-text warnings stay bilingual', async ({ page }) => {
  await mockWorkspace(page);
  let attempt = 0, previewRequest;
  await page.route('**/api/source-imports/providers', route => route.fulfill({ json: { zotero: { enabled: true, configured: true } } }));
  await page.route('**/api/source-imports/zotero/search', route => {
    attempt++;
    if (attempt === 1) return route.fulfill({ status: 504, json: { detail: 'Zotero MCP 响应超时，请确认 Zotero 已打开后重试。' } });
    return route.fulfill({ json: { items: attempt === 2 ? [] : [{ item_key: 'ABCD1234', title: '保留的文献标题', authors: '', date: '' }] } });
  });
  await page.route('**/api/source-imports/zotero/preview', route => {
    previewRequest = route.request().postDataJSON();
    return route.fulfill({ json: {
      source_type: 'mcp', source_key: 'zotero:local:0:ABCD1234', title: '保留的文献标题', summary: '', body_md: '原始元数据',
      suggested_kind: 'resource', tags: [], metadata: { import_provider: 'zotero' }, possible_duplicates: [],
      warnings: ['未读取到 Zotero 全文；请检查附件是否已下载并完成全文索引。当前预览保留元数据。']
    } });
  });
  await page.goto('/imports');
  await page.getByLabel('来源类型').selectOption('zotero');
  await page.getByRole('textbox', { name: 'Zotero 搜索词' }).fill('机器人');
  await page.getByRole('button', { name: '搜索 Zotero 文献' }).click();
  await expect(page.getByRole('alert')).toContainText('Zotero MCP 响应超时');
  await page.getByRole('combobox', { name: '界面语言' }).selectOption('en');
  await expect(page.getByRole('alert')).toContainText('Zotero MCP timed out.');
  await page.getByRole('button', { name: 'Search Zotero library' }).click();
  await expect(page.getByRole('status')).toContainText('No matching items found.');
  await page.getByRole('button', { name: 'Search Zotero library' }).click();
  await page.getByLabel('Include indexed full text in the preview when available').uncheck();
  await page.getByRole('button', { name: 'Preview item: 保留的文献标题' }).click();
  expect(previewRequest.include_fulltext).toBe(false);
  await expect(page.locator('.warning-box')).toContainText('No Zotero full text was available.');
  await page.getByRole('combobox', { name: 'Interface language' }).selectOption('zh');
  await expect(page.locator('.warning-box')).toContainText('未读取到 Zotero 全文');
  await expect(page.getByRole('textbox', { name: 'Markdown 正文' })).toHaveValue('原始元数据');
});
