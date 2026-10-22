import {test, expect} from '@playwright/test'

// Every scenario uses a fresh workspace in the disposable test database.
test.beforeEach(async ({page, request}) => {
  const response = await request.post('/api/auth/register', {data:{email:`merge-${Date.now()}-${Math.random().toString(36).slice(2)}@example.test`,display_name:'Merge regression',password:'test-password-123'}});
  expect(response.status()).toBe(201);
  await page.context().addCookies((await request.storageState()).cookies);
});

// Creates records through the API; run against an isolated database (scripts/run_e2e.py does that).
const stamp = Date.now()
const note = async (request, title, extra = {}) => (await (await request.post('/api/objects', {data: {kind: 'concept', title, ...extra}})).json())

test('evidence health lists findings with a way to the notes, and checks links in the background', async ({page, request}) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message))
  const a = await note(request, `0健康甲${stamp}`), b = await note(request, `0健康乙${stamp}`), c = await note(request, `0健康丙${stamp}`)
  await note(request, `0健康资料${stamp}`, {kind: 'resource', source_url: 'http://127.0.0.1:9/never'})   // local addresses are skipped, so no network is needed
  await request.post('/api/relations', {data: {source_id: a.id, target_id: b.id, relation_type: 'uses'}})
  await request.post('/api/relations', {data: {source_id: b.id, target_id: c.id, relation_type: 'supports', evidence: [{source_url: 'https://example.com/p', locator: '第 2 节'}]}})
  await request.post('/api/relations', {data: {source_id: a.id, target_id: c.id, relation_type: 'questions', evidence: [{source_url: 'https://example.com/q'}]}})
  await page.goto('/health')
  await expect(page.getByRole('heading', {name: '证据健康'})).toBeVisible()
  await expect(page.getByText(/证据覆盖率（\d+ \/ \d+ 条关系有证据）/)).toBeVisible()
  await page.getByRole('button', {name: /关系没有证据/}).click()
  const missing = page.locator('.health-finding').filter({hasText: `《0健康甲${stamp}》使用《0健康乙${stamp}》：没有任何证据。`})
  await expect(missing).toBeVisible()
  await expect(missing.getByRole('link', {name: `0健康甲${stamp}`})).toHaveAttribute('href', `/knowledge/${a.id}`)
  await page.getByRole('button', {name: /被支持也被质疑的结论/}).click()
  await expect(page.locator('.health-finding').filter({hasText: `《0健康丙${stamp}》被 1 个来源支持，也被 1 个来源质疑。`})).toBeVisible()
  await page.getByRole('button', {name: /失效链接/}).click()
  await expect(page.getByText('还没有检查过链接，点“检查链接”开始。')).toBeVisible()
  await page.getByRole('button', {name: '检查链接'}).click()
  await expect(page.getByText(/个无法判断/)).toBeVisible({timeout: 30000})
  await expect(page.getByText(/上次检查：/)).toBeVisible()
  await page.getByLabel('过期天数').selectOption('90')
  await expect(page.getByRole('navigation', {name: '检查项'})).toContainText('资料可能已过期')
  expect(errors).toEqual([])
})

test('a check with many findings is paged', async ({page, request}) => {
  const notes = []
  for (let start = 0; start < 26; start += 13) {
    await Promise.all(Array.from({length: 13}, async (_, i) => notes.push(await note(request, `分页健康${stamp}-${start + i}`))))
  }
  for (let i = 0; i < 25; i++) await request.post('/api/relations', {data: {source_id: notes[i].id, target_id: notes[i + 1].id, relation_type: 'depends_on'}})
  const summary = await (await request.get('/api/evidence-health')).json()
  const count = summary.checks.find(c => c.id === 'relations_without_evidence').count   // other tests share this database
  expect(count).toBeGreaterThanOrEqual(25)
  await page.goto('/health')
  await page.getByRole('button', {name: /关系没有证据/}).click()
  await expect(page.locator('.health-finding')).toHaveCount(20)
  await expect(page.getByRole('status').filter({hasText: `共 ${count} 条`})).toHaveText(`第 1–20 条，共 ${count} 条`)
  await page.getByRole('button', {name: '下一页'}).click()
  await expect(page.locator('.health-finding')).toHaveCount(Math.min(20, count - 20))
  await page.getByRole('button', {name: /依赖关系成环/}).click()                 // switching checks starts again at the first page
  await expect(page.getByRole('status').filter({hasText: '第 21–'})).toHaveCount(0)
})
