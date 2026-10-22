import {test, expect} from '@playwright/test'

// Every scenario uses a fresh workspace in the disposable test database.
test.beforeEach(async ({page, request}) => {
  const response = await request.post('/api/auth/register', {data:{email:`merge-${Date.now()}-${Math.random().toString(36).slice(2)}@example.test`,display_name:'Merge regression',password:'test-password-123'}});
  expect(response.status()).toBe(201);
  await page.context().addCookies((await request.storageState()).cookies);
});

// Creates records through the API; run against an isolated database (scripts/run_e2e.py does that).
const stamp = Date.now()
const bulk = async (request, count, make) => {
  for (let start = 0; start < count; start += 10) {
    await Promise.all(Array.from({length: Math.min(10, count - start)}, (_, i) => make(start + i)))
  }
}

test('knowledge list pages through results and returns to the first page when the search changes', async ({page, request}) => {
  await bulk(request, 30, i => request.post('/api/objects', {data: {kind: 'concept', title: `分页验收${stamp}-${String(i).padStart(2, '0')}`}}))
  await page.goto('/knowledge')
  await page.getByLabel('搜索知识').fill(`分页验收${stamp}`)
  await expect(page.getByRole('status').filter({hasText: '共 30 条'})).toHaveText('第 1–24 条，共 30 条')
  await expect(page.locator('.knowledge-card')).toHaveCount(24)
  await expect(page.getByRole('button', {name: '上一页'})).toBeDisabled()
  await page.getByRole('button', {name: '下一页'}).click()
  await expect(page.getByRole('status').filter({hasText: '共 30 条'})).toHaveText('第 25–30 条，共 30 条')
  await expect(page.locator('.knowledge-card')).toHaveCount(6)
  await expect(page.getByRole('button', {name: '下一页'})).toBeDisabled()
  await page.getByLabel('搜索知识').fill(`分页验收${stamp}-0`)
  await expect(page.locator('.knowledge-card')).toHaveCount(10)
  await expect(page.getByRole('navigation', {name: '分页'})).toHaveCount(0)
})

test('trash is paged, and restoring the last rows of a page falls back to the previous page', async ({page, request}) => {
  const made = []
  await bulk(request, 52, async i => made.push(await (await request.post('/api/objects', {data: {kind: 'concept', title: `回收分页${stamp}-${i}`}})).json()))
  await bulk(request, 52, i => request.delete(`/api/objects/${made[i].id}`))
  await page.goto('/trash')
  await expect(page.getByRole('status').filter({hasText: '共'})).toContainText('第 1–50 条')
  await expect(page.locator('.record-row')).toHaveCount(50)
  await page.getByRole('button', {name: '下一页'}).click()
  const rows = page.locator('.record-row')
  await expect(rows).toHaveCount(2)                                 // 52 rows: the second page holds the last two
  await rows.first().getByRole('button', {name: '恢复'}).click()
  await expect(rows).toHaveCount(1)
  await rows.first().getByRole('button', {name: '恢复'}).click()   // empties page 2
  await expect(rows).toHaveCount(50)                                // falls back to page 1
  await expect(page.getByRole('button', {name: '上一页'})).toHaveCount(0)
})

test('timeline shows the latest records and loads more on request', async ({page, request}) => {
  await bulk(request, 205, i => request.post('/api/sessions', {data: {objective: `轨迹分页${stamp}-${i}`}}))
  await page.goto('/timeline')
  const notice = page.getByRole('status').filter({hasText: '只显示最近的 200 条学习记录'})
  await expect(notice).toBeVisible()
  await notice.getByRole('button', {name: '再加载 200 条'}).click()
  await expect(page.getByRole('status').filter({hasText: '只显示最近的'})).toHaveCount(0)
  await expect(page.getByRole('heading', {name: new RegExp(`轨迹分页${stamp}-0$`)})).toBeVisible()
})

test('home counts everything but loads only a few rows', async ({page, request}) => {
  await bulk(request, 30, i => request.post('/api/objects', {data: {kind: 'question', title: `首页问题${stamp}-${i}`}}))
  const total = (await request.get('/api/objects?limit=1')).headers()['x-total-count']
  await page.goto('/')
  await expect(page.locator('.stat-card').first().locator('strong')).toHaveText(total)
  await expect(page.locator('.focus-row')).toHaveCount(4)   // however many questions there are
})

test('the whole graph says how many nodes it left out', async ({page, request}) => {
  test.setTimeout(120000)
  await bulk(request, 1010, i => request.post('/api/objects', {data: {kind: 'concept', title: `大图节点${stamp}-${i}`}}))
  const total = Number((await request.get('/api/objects?limit=1')).headers()['x-total-count'])   // other tests share this database
  await page.goto('/graph')
  await expect(page.locator('.graph-note')).toContainText(`仅显示关联最多的 300 个节点，另有 ${total - 300} 个未显示`)
  await expect(page.locator('.graph-container')).toHaveAttribute('data-node-count', '300')
})
