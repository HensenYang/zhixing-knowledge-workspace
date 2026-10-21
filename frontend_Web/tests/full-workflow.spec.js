import {test, expect} from '@playwright/test';
import fs from 'node:fs/promises';

// Run only against a disposable backend. See scripts/verify_full.py.
test.beforeEach(async ({page}) => {
  if (process.env.WORKSPACE_DISPOSABLE_TEST !== '1') throw Error('Run with scripts/verify_full.py against its disposable database.');
  const response = await page.request.post('/api/auth/register', {data:{
    email:'workflow-'+crypto.randomUUID()+'@example.test', display_name:'完整流程测试', password:'workflow-test-password'
  }});
  expect(response.status(), await response.text()).toBe(201);
});

function samplePdf() {
  const stream='BT /F1 12 Tf 60 740 Td (Scientific learning material: observations, evidence and reproducibility.) Tj ET';
  const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>','<< /Length '+stream.length+' >>\nstream\n'+stream+'\nendstream'];
  let content='%PDF-1.4\n'; const offsets=[0];
  objects.forEach((object,index)=>{offsets.push(Buffer.byteLength(content));content+=(index+1)+' 0 obj\n'+object+'\nendobj\n';});
  const start=Buffer.byteLength(content);
  content+='xref\n0 6\n0000000000 65535 f \n'+offsets.slice(1).map(offset=>String(offset).padStart(10,'0')+' 00000 n \n').join('');
  content+='trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+start+'\n%%EOF\n';
  return Buffer.from(content);
}

test('real PDF import previews without writes, commits edited fields and preserves the original attachment', async ({page}) => {
  await page.goto('/imports');
  await page.getByLabel('来源类型').selectOption('pdf');
  await page.getByLabel('选择 PDF', {exact:true}).setInputFiles({name:'learning-material.pdf', mimeType:'application/pdf', buffer:samplePdf()});
  await page.getByRole('button', {name:'提取并预览'}).click();
  await expect(page.getByLabel('Markdown 正文')).toHaveValue(/Scientific learning material/);
  expect(await (await page.request.get('/api/objects')).json()).toHaveLength(0);
  await page.getByRole('textbox', {name:'标题',exact:true}).fill('科学传播：导入的学习资料');
  await page.getByLabel('摘要', {exact:true}).fill('从资料中识别观察、证据和复现要求。');
  await page.getByLabel('标签（逗号分隔）').fill('科学传播, 真实导入');
  await page.getByRole('button', {name:'确认并创建知识对象'}).click();
  await expect(page.getByText('资料已导入。', {exact:true})).toBeVisible();
  await page.getByRole('link', {name:'打开已导入资料'}).click();
  await expect(page.getByLabel('笔记标题')).toHaveValue('科学传播：导入的学习资料');
  const id=new URL(page.url()).pathname.split('/').at(-1);
  const object=await (await page.request.get('/api/objects/'+id)).json();
  expect(object.summary).toContain('观察、证据'); expect(object.tags.slice().sort()).toEqual(['科学传播','真实导入'].sort());
  expect(object.body_md).toContain('Scientific learning material');
  const attachments=await (await page.request.get('/api/objects/'+id+'/attachments')).json();
  expect(attachments.filter(item=>item.mime_type==='application/pdf')).toHaveLength(1);
  const file=await page.request.get('/api/attachments/'+attachments.find(item=>item.mime_type==='application/pdf').id);
  expect((await file.body()).subarray(0,5).toString()).toBe('%PDF-');
  await page.reload(); await expect(page.locator('.editor-panel .markdown')).toContainText('Scientific learning material');
});

test('a new note autosaves bilingual drafts, survives reload and appears in search and revision history', async ({page}) => {
  await page.goto('/knowledge'); await page.getByRole('button', {name:'新建笔记'}).click();
  await expect(page.getByLabel('笔记正文')).toBeVisible();
  const id=new URL(page.url()).pathname.split('/').at(-1);
  const body='# 可复现科学\n\n保留中文内容与 English terms。公式 $E=mc^2$。\n\n```python\nprint("evidence")\n```';
  await page.getByLabel('笔记标题').fill('可复现科学：新增知识笔记');
  await page.getByLabel('笔记正文').fill(body);
  await page.getByRole('combobox', {name:'界面语言'}).selectOption('en');
  await expect(page.getByLabel('Note body')).toHaveValue(body);
  await expect(page.locator('.save-status')).toHaveText('Saved', {timeout:15000});
  await page.reload(); await expect(page.getByLabel('Note body')).toHaveValue(body);
  await page.getByLabel('Note title').fill('可复现科学：修订后的知识笔记');
  await expect(page.locator('.save-status')).toHaveText('Saved', {timeout:15000});
  const object=await (await page.request.get('/api/objects/'+id)).json();
  expect(object.body_md).toBe(body); expect(object.title).toContain('修订后'); expect(object.version).toBeGreaterThan(1);
  const revisions=await (await page.request.get('/api/objects/'+id+'/revisions')).json();
  expect(revisions.some(item=>item.snapshot.title==='可复现科学：新增知识笔记')).toBe(true);
  await page.getByRole('button', {name:'Read',exact:true}).click(); await expect(page.locator('.katex').first()).toBeVisible();
  await page.goto('/knowledge'); await page.getByLabel('Search knowledge').fill('可复现科学');
  await expect(page.getByRole('heading', {name:object.title})).toBeVisible();
});

test('a real learning path reorders steps, publishes, exports and imports independent copies with graph evidence', async ({page,browser}) => {
  test.setTimeout(90000);
  const nodes=[];
  for(const title of ['科学方法基础','证据与复现实验']) {
    const response=await page.request.post('/api/objects',{data:{kind:'concept',title,summary:'用于教学的关键概念',body_md:'原始知识正文 '+title,tags:['科学教育']}});
    expect(response.status()).toBe(201); nodes.push(await response.json());
  }
  const edge=await page.request.post('/api/relations',{data:{source_id:nodes[1].id,target_id:nodes[0].id,relation_type:'depends_on',description:'实验依赖基本科学方法',evidence:[{evidence_object_id:nodes[0].id,locator:'课程第 1 节',explanation:'先掌握观察与假设。'}]}});
  expect(edge.status()).toBe(201);
  await page.goto('/paths'); await page.getByLabel('新学习路径名称').fill('从科学方法到可复现实验');
  await page.getByRole('button',{name:'新建学习路径'}).click(); await expect(page.getByLabel('学习目标')).toBeVisible();
  const id=new URL(page.url()).pathname.split('/').at(-1);
  await page.getByLabel('学习目标').fill('能够解释假设、证据和复现。');
  await page.getByLabel('路径完成条件').fill('独立完成一次可复现实验。');
  for(const [index,node] of nodes.entries()) {
    await page.getByLabel('选择知识对象').selectOption(node.id); await page.getByRole('button',{name:'加入知识对象'}).click();
    await page.getByLabel('步骤 '+(index+1)+' 讲解提示').fill('阅读 '+node.title+' 并提出问题。');
    await page.getByLabel('步骤 '+(index+1)+' 完成条件').fill('能够讲解 '+node.title+'。');
    await page.getByLabel('步骤 '+(index+1)+' 预计用时').fill(String((index+1)*15));
  }
  await page.getByRole('button',{name:'上移步骤 2',exact:true}).click();
  await page.getByRole('button',{name:'保存路径',exact:true}).click();
  await expect(page.getByText('学习路径已保存。',{exact:true})).toBeVisible();
  await page.reload(); await expect(page.getByLabel('步骤 1 标题')).toHaveValue(nodes[1].title);
  await expect(page.getByLabel('步骤 2 预计用时')).toHaveValue('15');
  await page.getByRole('button',{name:'发布分享',exact:true}).click();
  await expect(page.getByText('路径已发布，可以复制只读分享链接。')).toBeVisible();
  const published=await (await page.request.get('/api/learning-paths/'+id)).json();
  const publicContext=await browser.newContext({baseURL:new URL(page.url()).origin});
  try {
    const publicPage=await publicContext.newPage(); await publicPage.goto('/shared/paths/'+published.share_token);
    await expect(publicPage.getByRole('heading',{name:published.title,exact:true})).toBeVisible();
    await expect(publicPage.locator('.artifact-node')).toHaveCount(2);
    const publicData=await (await publicPage.request.get('/api/shared/learning-paths/'+published.share_token)).json();
    expect(publicData.artifact.objects.every(item=>item.body_md==='')).toBe(true);
    expect(publicData.artifact.relations[0].evidence[0].locator).toBe('课程第 1 节');
  } finally { await publicContext.close(); }
  await page.getByLabel('同时包含所选知识节点的正文（不包含附件文件）').check();
  await page.getByRole('button',{name:'保存并预览 Artifact',exact:true}).click();
  await expect(page.locator('.artifact-node')).toHaveCount(2);
  const downloadPromise=page.waitForEvent('download'); await page.getByRole('button',{name:'下载 JSON 文件包',exact:true}).click();
  const download=await downloadPromise; const content=await fs.readFile(await download.path()); const artifact=JSON.parse(content);
  expect(artifact.includes_body).toBe(true); expect(artifact.relations).toHaveLength(1);
  await page.goto('/artifacts'); await page.getByLabel('选择 HTML 或 JSON 学习路径文件').setInputFiles({name:'learning-path.json',mimeType:'application/json',buffer:content});
  await expect(page.locator('.artifact-node')).toHaveCount(2);
  await page.getByRole('button',{name:'保存副本到当前工作区',exact:true}).click();
  await expect(page).toHaveURL(/\/paths\/[^/]+$/); const copyId=new URL(page.url()).pathname.split('/').at(-1);
  expect(copyId).not.toBe(id);
  const copy=await (await page.request.get('/api/learning-paths/'+copyId)).json();
  expect(copy.status).toBe('draft'); expect(copy.share_token).toBeNull(); expect(copy.steps).toHaveLength(2);
  expect(copy.steps.every(step=>!nodes.some(node=>node.id===step.object_id))).toBe(true);
  const copyGraph=await (await page.request.get('/api/learning-paths/'+copyId+'/artifact?include_body=true')).json();
  expect(copyGraph.relations).toHaveLength(1); expect(copyGraph.relations[0].evidence[0].evidence_object_id).toBe(copy.steps[1].object_id);
  await page.goto('/paths/'+id); await page.getByRole('button',{name:'停止分享',exact:true}).click();
  await expect.poll(async()=> (await page.request.get('/api/shared/learning-paths/'+published.share_token)).status()).toBe(404);
});
