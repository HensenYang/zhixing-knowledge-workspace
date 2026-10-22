import {test, expect} from '@playwright/test'
import {randomUUID} from 'node:crypto'

// Restoring writes data: run against an isolated database (scripts/run_e2e.py does that).
const TABLES = ['objects', 'tags', 'object_tags', 'relations', 'relation_evidence', 'canvases', 'canvas_items', 'canvas_edges', 'learning_sessions',
  'session_objects', 'experiment_runs', 'run_artifacts', 'attachments', 'object_attachments', 'object_revisions', 'canvas_revisions']

const crcTable = Array.from({length: 256}, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0 })
const crc32 = buffer => { let c = 0xFFFFFFFF; for (const byte of buffer) c = crcTable[(c ^ byte) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0 }

// Smallest possible ZIP writer (stored entries), enough to hand the app a backup.
function zip(files) {
  const parts = [], central = []
  let offset = 0
  for (const [name, data] of Object.entries(files)) {
    const nameBuffer = Buffer.from(name), crc = crc32(data)
    const local = Buffer.alloc(30)
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(0x0800, 6); local.writeUInt32LE(crc, 14)
    local.writeUInt32LE(data.length, 18); local.writeUInt32LE(data.length, 22); local.writeUInt16LE(nameBuffer.length, 26)
    parts.push(local, nameBuffer, data)
    const entry = Buffer.alloc(46)
    entry.writeUInt32LE(0x02014b50, 0); entry.writeUInt16LE(20, 4); entry.writeUInt16LE(20, 6); entry.writeUInt16LE(0x0800, 8); entry.writeUInt32LE(crc, 16)
    entry.writeUInt32LE(data.length, 20); entry.writeUInt32LE(data.length, 24); entry.writeUInt16LE(nameBuffer.length, 28); entry.writeUInt32LE(offset, 42)
    central.push(entry, nameBuffer)
    offset += 30 + nameBuffer.length + data.length
  }
  const size = central.reduce((total, buffer) => total + buffer.length, 0)
  const end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(Object.keys(files).length, 8); end.writeUInt16LE(Object.keys(files).length, 10)
  end.writeUInt32LE(size, 12); end.writeUInt32LE(offset, 16)
  return Buffer.concat([...parts, ...central, end])
}

const backup = (id, title) => {
  const tables = Object.fromEntries(TABLES.map(name => [name, []]))
  tables.objects = [{id, kind: 'concept', title, summary: '', body_md: '备份里的正文', source_url: null, reading_status: 'unread', mastery_status: 'unknown',
    metadata: {}, version: 1, created_at: '2026-10-01T00:00:00+00:00', updated_at: '2026-10-01T00:00:00+00:00', archived_at: null, deleted_at: null}]
  return zip({'manifest.json': Buffer.from(JSON.stringify({format: 'embodied-knowledge', version: 1, created_at: '2026-10-01T00:00:00', tables, external_artifacts_included: false}))})
}

test('restoring a backup runs in the background and a repeated restore is refused as a conflict', async ({page, request}) => {
  const id = randomUUID(), title = `恢复验收${Date.now()}`
  const file = {name: 'backup.zip', mimeType: 'application/zip', buffer: backup(id, title)}
  await page.goto('/settings')
  await page.locator('input[type=file]').setInputFiles(file)
  await expect(page.getByText('备份检查结果')).toBeVisible()
  await expect(page.getByText('知识对象 1', {exact: false})).toBeVisible()
  await page.getByRole('button', {name: '恢复已检查的备份'}).click()
  await expect(page.getByText('恢复完成')).toBeVisible({timeout: 20000})
  const restored = await (await request.get(`/api/objects/${id}`)).json()
  expect(restored.title).toBe(title)
  const job = (await (await request.get('/api/jobs?kind=import&limit=1')).json())[0]
  expect(job).toMatchObject({status: 'succeeded', progress: 100})
  await page.reload()
  await page.locator('input[type=file]').setInputFiles(file)
  await expect(page.getByRole('alert')).toContainText('存在 ID 冲突')
  await expect(page.getByRole('button', {name: '恢复已检查的备份'})).toHaveCount(0)
})
