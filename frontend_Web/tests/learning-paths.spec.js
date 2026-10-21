import {test,expect} from '@playwright/test';

const object={id:'00000000-0000-4000-8000-000000000001',title:'VLA 基础',summary:'理解视觉、语言与动作的联合建模。',kind:'concept'};
const draft={
  id:'10000000-0000-4000-8000-000000000001',title:'VLA 入门路径',objective_md:'',description_md:'',completion_criteria_md:'',
  status:'draft',share_token:null,version:1,steps:[]
};

test('learning path can be composed, published and viewed read-only',async({page})=>{
  let saved=draft;
  await page.route('**/api/**',async route=>{
    const request=route.request(), url=new URL(request.url());
    let data;
    if(url.pathname==='/api/health') data={service:'ready',database:'ready',schema_version:'V004'};
    else if(url.pathname==='/api/objects') data=[object];
    else if(url.pathname===`/api/learning-paths/${draft.id}` && request.method()==='GET') data=saved;
    else if(url.pathname===`/api/learning-paths/${draft.id}` && request.method()==='PUT') {
      const body=request.postDataJSON();
      saved={...saved,...body,version:2,steps:body.steps.map((step,position)=>({...step,position,object_title:object.title,object_summary:object.summary,object_kind:object.kind,object_available:true}))};
      data=saved;
    } else if(url.pathname===`/api/learning-paths/${draft.id}/publish`) {
      saved={...saved,status:'published',share_token:'share_token_123456789',version:3}; data=saved;
    } else if(url.pathname==='/api/shared/learning-paths/share_token_123456789') data=saved;
    if(data) await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
    else await route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'not found'})});
  });

  await page.goto(`/paths/${draft.id}`);
  await page.getByLabel('学习目标').fill('能够解释 VLA 的输入、输出和训练目标。');
  await page.getByLabel('路径完成条件').fill('能够独立讲解，并写出一个最小流程。');
  await page.getByRole('button',{name:'加入知识对象'}).click();
  await page.getByLabel('步骤 1 讲解提示').fill('阅读概念笔记并画出数据流。');
  await page.getByLabel('步骤 1 完成条件').fill('能够不看笔记解释数据流。');
  await page.getByRole('button',{name:'发布分享'}).click();
  await expect(page.getByText('路径已发布，可以复制只读分享链接。')).toBeVisible();
  await expect(page.getByRole('button',{name:'复制分享链接'})).toBeVisible();

  await page.goto('/shared/paths/share_token_123456789');
  await expect(page.getByRole('heading',{name:'VLA 入门路径'})).toBeVisible();
  await expect(page.getByText('能够不看笔记解释数据流。')).toBeVisible();
  await expect(page.getByRole('button')).toHaveCount(0);
});
