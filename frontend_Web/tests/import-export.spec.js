import {test, expect} from '@playwright/test';

test('source import previews editable metadata and commits after confirmation', async ({page}) => {
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    let data = null;
    if (url.pathname === '/api/health') data = {service: 'ready', database: 'ready', schema_version: 'V003'};
    else if (url.pathname === '/api/source-imports/providers') data = {providers: ['arxiv', 'doi', 'github', 'pdf'], mcp: {enabled: true, tool: 'import_source'}};
    else if (url.pathname === '/api/source-imports/preview') data = {
      source_type: 'arxiv', source_key: '2401.01234', source_url: 'https://arxiv.org/abs/2401.01234',
      title: 'Imported Paper', summary: 'An abstract', body_md: '## 摘要\n\nContent',
      suggested_kind: 'resource', tags: ['arXiv'], metadata: {arxiv: '2401.01234'}, warnings: [], possible_duplicates: []
    };
    else if (url.pathname === '/api/source-imports/commit') data = {id: 'imported-1', title: 'Edited Imported Paper'};
    if (data) await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(data)});
    else await route.fulfill({status: 404, contentType: 'application/json', body: '{}'});
  });
  await page.goto('/imports');
  await expect(page.getByRole('heading', {name: '资料导入'})).toBeVisible();
  await page.getByLabel('资料地址').fill('https://arxiv.org/abs/2401.01234');
  await page.getByRole('button', {name: '提取并预览'}).click();
  await expect(page.getByDisplayValue('Imported Paper')).toBeVisible();
  await page.getByDisplayValue('Imported Paper').fill('Edited Imported Paper');
  await page.getByRole('button', {name: '确认并创建知识对象'}).click();
  await expect(page.getByText('资料已导入。')).toBeVisible();
  await expect(page.getByRole('link', {name: '打开已导入资料'})).toHaveAttribute('href', '/knowledge/imported-1');
});
