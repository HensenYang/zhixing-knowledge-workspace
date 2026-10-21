import {test,expect} from '@playwright/test';
const suffix = crypto.randomUUID().slice(0,8);

test.beforeEach(async({page},testInfo)=>{
  const email=`record-${suffix}-${testInfo.workerIndex}-${testInfo.repeatEachIndex}@example.test`;
  const data={email,display_name:'记录测试',password:'browser-test-password'};
  const registered=await page.request.post('/api/auth/register',{data});
  if(!registered.ok() && registered.status()!==409) throw new Error(await registered.text());
  if(registered.status()===409) await page.request.post('/api/auth/login',{data});
});

async function create(request,title,kind='concept') {
  const response=await request.post('/api/objects',{data:{title,kind,body_md:'保留原有正文',tags:['保留标签'],metadata:{keep:true}}});
  expect(response.ok()).toBeTruthy(); return response.json();
}
async function confirm(page) { await page.getByRole('dialog',{name:'确认删除'}).getByRole('button',{name:'确认删除',exact:true}).click(); }

test('trash permanent delete requires confirmation and cannot be restored',async({page}) => {
  const request=page.request;
  const obj=await create(request,`永久删除验收 ${suffix}`);
  await request.delete(`/api/objects/${obj.id}`);
  await page.goto('/trash');
  const row=page.locator('.record-row').filter({hasText:obj.title});
  await row.getByRole('button',{name:'永久删除',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'确认永久删除'})).toContainText('此操作无法撤销');
  await page.getByRole('button',{name:'取消',exact:true}).click(); await expect(row).toHaveCount(1);
  await row.getByRole('button',{name:'永久删除',exact:true}).click();
  await page.getByRole('button',{name:'确认永久删除',exact:true}).click(); await expect(row).toHaveCount(0);
  expect((await request.post(`/api/trash/object/${obj.id}/restore`,{data:{}})).status()).toBe(404);
});

test('graph edits nodes and relations, deletes and restores connections',async({page}) => {
  const request=page.request;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const a=await create(request,`CRUD${suffix}图谱起点`),b=await create(request,`CRUD${suffix}图谱终点`);
  const relation=await (await request.post('/api/relations',{data:{source_id:a.id,target_id:b.id,relation_type:'uses',evidence:[{source_url:'https://example.com',locator:'第一章'}]}})).json();
  await page.goto('/graph'); await page.getByRole('button',{name:'节点列表',exact:true}).click();
  await page.locator('.record-row').filter({hasText:a.title}).getByRole('button',{name:'修改节点'}).click();
  await page.getByLabel('节点名称').fill(`CRUD${suffix}图谱起点已修改`); await page.getByLabel('节点摘要').fill('新增摘要');
  await page.getByRole('button',{name:'保存节点'}).click();
  await expect(page.locator('.graph-details')).toContainText(`CRUD${suffix}图谱起点已修改`);
  const updated=await (await request.get(`/api/objects/${a.id}`)).json(); expect(updated.body_md).toBe('保留原有正文'); expect(updated.metadata.keep).toBe(true);
  await page.getByRole('button',{name:'关系列表',exact:true}).click();
  const row=page.locator('.record-row').filter({hasText:`CRUD${suffix}图谱起点已修改`}); await row.getByRole('button',{name:'修改关系'}).click();
  await page.getByLabel('为什么建立这条关系？').fill('修改后的连接说明'); await page.getByRole('button',{name:'保存关系'}).click();
  await expect(row).toContainText('修改后的连接说明'); await row.getByRole('button',{name:'删除',exact:true}).click(); await confirm(page);
  await expect(row).toHaveCount(0); await page.getByRole('button',{name:'撤销删除'}).click(); await expect(row).toHaveCount(1);
  const restored=(await (await request.get('/api/relations')).json()).find(r=>r.id===relation.id); expect(restored.evidence[0].locator).toBe('第一章');
  await page.getByRole('button',{name:'节点列表',exact:true}).click();
  const node=page.locator('.record-row').filter({hasText:`CRUD${suffix}图谱起点已修改`}); await node.getByRole('button',{name:'删除',exact:true}).click(); await confirm(page); await expect(node).toHaveCount(0);
  await page.getByRole('link',{name:'回收站',exact:true}).click(); const trash=page.locator('.record-row').filter({hasText:`CRUD${suffix}图谱起点已修改`}); await trash.getByRole('button',{name:'恢复',exact:true}).click(); await expect(trash).toHaveCount(0);
  expect((await (await request.get('/api/relations')).json()).some(r=>r.id===relation.id)).toBe(true); expect(errors).toEqual([]);
});

test('canvas rename, log edit and run delete are recoverable',async({page}) => {
  const request=page.request;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const canvas=await (await request.post('/api/canvases',{data:{title:`CRUD${suffix}画布`}})).json();
  await page.goto('/canvases'); const card=page.locator('.canvas-card').filter({hasText:`CRUD${suffix}画布`});
  page.once('dialog',dialog=>dialog.accept(`CRUD${suffix}画布已改名`)); await card.getByRole('button',{name:'重命名'}).click(); await expect(card).toContainText(`CRUD${suffix}画布已改名`);
  await card.getByRole('button',{name:'删除',exact:true}).click(); await confirm(page); await expect(card).toHaveCount(0); await page.getByRole('button',{name:'撤销删除'}).click(); await expect(card).toHaveCount(1);
  const session=await (await request.post('/api/sessions',{data:{objective:`CRUD${suffix}学习记录`,activity_md:'原活动',understanding_change_md:'原理解'}})).json();
  await page.goto('/timeline'); let event=page.locator('.timeline-event').filter({hasText:`CRUD${suffix}学习记录`}); await event.getByRole('button',{name:'修改',exact:true}).click();
  await page.getByLabel('目标',{exact:true}).fill(`CRUD${suffix}学习记录已修改`); await page.getByLabel('理解变化').fill('新的理解'); await page.getByRole('button',{name:'保存记录',exact:true}).click();
  event=page.locator('.timeline-event').filter({hasText:`CRUD${suffix}学习记录已修改`}); await expect(event).toContainText('新的理解'); await expect(event).toContainText('原活动');
  await event.getByRole('button',{name:'删除',exact:true}).click(); await confirm(page); await expect(event).toHaveCount(0); await page.getByRole('button',{name:'撤销删除'}).click(); await expect(event).toHaveCount(1);
  const experiment=await create(request,`CRUD${suffix}实验主题`,'experiment'); const run=await (await request.post('/api/runs',{data:{experiment_id:experiment.id,hypothesis_md:`CRUD${suffix}假设`,artifacts:[{location:'first.log'},{location:'second.log'}]}})).json();
  await page.goto('/experiments'); const runCard=page.locator('.run-card').filter({hasText:`CRUD${suffix}假设`}); await runCard.getByRole('button',{name:'修改',exact:true}).click(); await page.getByLabel('结果与结论').fill(`CRUD${suffix}新结果`); await page.getByRole('button',{name:'保存运行记录'}).click();
  const saved=(await (await request.get('/api/runs')).json()).find(r=>r.id===run.id); expect(saved.artifacts).toHaveLength(2);
  const updatedRun=page.locator('.run-card').filter({hasText:`CRUD${suffix}新结果`}); await updatedRun.getByRole('button',{name:'删除',exact:true}).click(); await confirm(page); await expect(updatedRun).toHaveCount(0); await page.getByRole('button',{name:'撤销删除'}).click(); await expect(updatedRun).toHaveCount(1);
  expect(errors).toEqual([]);
});
