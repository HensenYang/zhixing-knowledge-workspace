import {test, expect} from '@playwright/test';

const objects = ['VLA', 'VLM', 'Flow Matching', 'WLA', '研究任务'].map((title, index) => ({
  id: `reading-${index}`, title, kind: index === 4 ? 'task' : 'model', summary: '', body_md: `# ${title}`,
  source_url: '', reading_status: 'unread', mastery_status: 'unknown', metadata: {}, tags: [], version: 1, archived_at: null
}));
const relations = [
  {id: 'r0', source_id: objects[0].id, target_id: objects[1].id, relation_type: 'depends_on', description: '以视觉语言模型为基座'},
  {id: 'r1', source_id: objects[0].id, target_id: objects[2].id, relation_type: 'uses', description: '使用流匹配动作头'},
  {id: 'r2', source_id: objects[0].id, target_id: objects[3].id, relation_type: 'compares_with', description: '对比两条动作策略路线'},
  {id: 'r3', source_id: objects[4].id, target_id: objects[0].id, relation_type: 'uses', description: '任务研究当前模型'}
];
test.beforeEach(async ({page}) => {
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    let data = [];
    if (url.pathname === '/api/health') data = {database: 'ready'};
    else if (url.pathname === '/api/auth/me') data = {id:'mock-user',email:'reader@example.test',display_name:'阅读测试',workspaces:[{id:'mock-workspace',name:'阅读测试空间',role:'owner'}]};
    else if (url.pathname === '/api/comments' || url.pathname === '/api/reviews') data = [];
    else if (url.pathname === '/api/objects') data = objects;
    else if (url.pathname === '/api/relations') data = relations;
    else if (url.pathname === '/api/graph') data = {nodes: objects, edges: relations};
    else if (/\/api\/objects\/reading-\d$/.test(url.pathname)) data = objects.find(object => object.id === url.pathname.split('/').at(-1));
    return route.fulfill({json: data});
  });
});
test('relation reading follows position, preserves visits and returns to the prior note', async ({page}) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/knowledge/reading-0');
  const panel = page.getByRole('region', {name: '沿关系阅读'});
  await expect(panel.locator('.reading-position')).toContainText('VLA');
  await expect(panel.locator('.graph-container')).toHaveAttribute('data-node-count', '5');
  await expect(panel.locator('.reading-neighbors')).toContainText('前置知识／基座');
  await expect(panel.locator('.reading-neighbors')).toContainText('使用当前的模型／方法');
  await panel.locator('.reading-neighbors').getByRole('link', {name: /VLM/}).click();
  await expect(panel.locator('.graph-container')).toHaveAttribute('data-center', 'reading-1');
  await expect(panel.locator('.reading-trail [aria-current]')).toHaveText('VLM · 当前');
  await panel.getByRole('button', {name: '展开', exact: true}).click();
  const dialog = page.getByRole('dialog', {name: '展开局部图谱'});
  await expect(dialog.locator('.graph-container')).toHaveAttribute('data-center', 'reading-1');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(panel.locator('.reading-neighbors')).toContainText('依赖当前的后续内容');
  await page.reload();
  await expect(panel.locator('.reading-trail')).toContainText('VLA');
  await expect(panel.locator('.reading-trail [aria-current]')).toHaveText('VLM · 当前');
  await page.getByRole('button', {name: '← 返回上一页'}).click();
  await expect(panel.locator('.graph-container')).toHaveAttribute('data-center', 'reading-0');
  await panel.getByRole('button', {name: '重新开始路径'}).click();
  await expect(panel.locator('.reading-trail li')).toHaveCount(1);
  expect(errors).toEqual([]);
});
test('relation and direction filters affect both neighbor links and local graph', async ({page}) => {
  await page.goto('/knowledge/reading-0');
  const panel = page.getByRole('region', {name: '沿关系阅读'});
  await page.getByLabel('阅读关系类型').selectOption('uses');
  await expect(panel.locator('.graph-container')).toHaveAttribute('data-node-count', '3');
  await page.getByLabel('阅读连接方向').selectOption('incoming');
  await expect(panel.locator('.reading-neighbors a')).toHaveCount(1);
  await expect(panel.locator('.reading-neighbors')).toContainText('研究任务');
  await expect(panel.locator('.graph-container')).toHaveAttribute('data-node-count', '2');
  await page.getByLabel('阅读连接方向').selectOption('outgoing');
  await expect(panel.locator('.reading-neighbors')).toContainText('Flow Matching');
  await expect(panel.locator('.graph-container')).toHaveAttribute('data-edge-count', '1');
  await page.getByLabel('阅读关系类型').selectOption('compares_with');
  await expect(panel.locator('.reading-neighbors')).toContainText('WLA');
  await panel.locator('.reading-neighbors').getByRole('link').click();
  await expect(panel.locator('.graph-container')).toHaveAttribute('data-center', 'reading-3');
  await expect(page.getByLabel('阅读关系类型')).toHaveValue('compares_with');
  await expect(panel.locator('.reading-neighbors')).toContainText('VLA');
});
