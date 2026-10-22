import { test, expect } from '@playwright/test';
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWq8AAAAASUVORK5CYII=','base64');
const imageId='11111111-1111-4111-8111-111111111111';
const fileId='22222222-2222-4222-8222-222222222222';
const token='a'.repeat(32);

test('PDF preview shows staged images and confirms one atomic import without duplicate PDF upload', async({page})=>{
  const calls=[];
  const assets=[{id:imageId,filename:'page-1-image.png',mime_type:'image/png',kind:'image',page:1,preview_url:`/api/source-imports/assets/${token}/${imageId}`},
    {id:fileId,filename:'original.pdf',mime_type:'application/pdf',kind:'source',page:null,preview_url:`/api/source-imports/assets/${token}/${fileId}`}];
  await page.route('**/api/**',route=>{
    if (new URL(route.request().url()).pathname === '/api/auth/me') return route.fulfill({json:{id:'mock-user',email:'test@example.test',display_name:'Test user',workspaces:[{id:'mock-workspace',name:'Test workspace',role:'owner'}]}});
    const request=route.request(),path=new URL(request.url()).pathname;
    calls.push({path,method:request.method(),body:path.endsWith('/commit')?request.postDataJSON():null});
    if(path.includes('/assets/'))return route.fulfill({contentType:'image/png',body:png});
    const data=path==='/api/health'?{database:'ready',service:'ready'}
      :path.endsWith('/providers')?{mcp:{enabled:false}}
      :path.endsWith('/preview-file')?{source_type:'pdf',source_key:'pdf-hash',title:'原始 PDF 标题',summary:'',body_md:`## 第 1 页\n\nOriginal text\n\n![原始图片](import-asset://${imageId})`,suggested_kind:'resource',metadata:{},tags:[],warnings:[],possible_duplicates:[],preview_token:token,assets}
      :path.endsWith('/commit')?{id:'saved-media'}:[];
    return route.fulfill({json:data});
  });
  await page.goto('/imports');
  await page.getByLabel('来源类型').selectOption('pdf');
  await page.getByLabel('选择 PDF',{exact:true}).setInputFiles({name:'original.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-test')});
  await page.getByRole('button',{name:'提取并预览'}).click();
  await expect(page.getByRole('region',{name:'待保存的图片与附件'})).toContainText('已提取 1 张图片');
  await expect(page.locator('.import-rendered-preview img')).toHaveAttribute('src',assets[0].preview_url);
  await expect(page.locator('.import-rendered-preview img')).toBeVisible();
  await page.getByRole('textbox',{name:'标题',exact:true}).fill('用户修改后的标题');
  await page.getByRole('combobox',{name:'界面语言'}).selectOption('en');
  await expect(page.getByRole('region',{name:'Images and attachments to save'})).toContainText('Extracted 1 images');
  await expect(page.getByRole('textbox',{name:'Title',exact:true})).toHaveValue('用户修改后的标题');
  expect(calls.some(call=>call.path.endsWith('/commit'))).toBe(false);
  await page.getByRole('button',{name:'Confirm and create knowledge object'}).click();
  await expect(page.getByRole('link',{name:'Open imported material'})).toHaveAttribute('href','/knowledge/saved-media');
  const payload=calls.find(call=>call.path.endsWith('/commit')).body;
  expect(payload.preview_token).toBe(token);
  expect(payload.object.body_md).toContain(`import-asset://${imageId}`);
  expect(payload.object.title).toBe('用户修改后的标题');
  expect(calls.some(call=>/\/objects\/.*\/attachments/.test(call.path))).toBe(false);
});

test('reading renders sanitized README HTML and resolves image paths without rewriting stored content',async({page})=>{
  const body=`<p align="center"><h1 align="center">用户的 HTML 标题</h1></p>
<p align="center"><img src="./pics/icon/title.jpg" alt="课程封面" width="48%" /></p>
<details open><summary>原始说明</summary><p>保留的 HTML 正文</p></details>
<a href="#section">Jump to section</a>

## Section

| Name | Value |
| --- | --- |
| Original | 42 |

Formula $a_t = \\pi(o_t)$.

- [x] Completed original task

<script>window.__unsafe = true</script><iframe src="https://example.org"></iframe>
<a href="javascript:window.__unsafe=true">Unsafe link</a><img src="./evil.png" onerror="window.__unsafe=true" alt="test" />`;
  const note={id:'html-note',title:'保留的用户标题',kind:'repository',summary:'',body_md:body,source_url:'https://github.com/Lordog/dive-into-llms',metadata:{commit:'f84c04268794ef94f8949808bbc14ab8636763a0',readme_path:'README.md'},version:1,tags:[],reading_status:'reading',mastery_status:'unknown',archived_at:null};
  let writes=0;
  await page.route('**/raw.githubusercontent.com/**',route=>route.fulfill({contentType:'image/png',body:png}));
  await page.route('**/api/**',route=>{
    if (new URL(route.request().url()).pathname === '/api/auth/me') return route.fulfill({json:{id:'mock-user',email:'test@example.test',display_name:'Test user',workspaces:[{id:'mock-workspace',name:'Test workspace',role:'owner'}]}});
    const request=route.request(),path=new URL(request.url()).pathname;
    if(request.method()!=='GET')writes++;
    const data=path==='/api/health'?{database:'ready',service:'ready'}:path==='/api/objects/html-note'?note:path==='/api/objects'?[note]:path==='/api/graph'?{nodes:[note],edges:[]}:[];
    return route.fulfill({json:data});
  });
  await page.goto('/knowledge/html-note');
  const markdown=page.locator('.editor-panel .markdown');
  await expect(markdown.getByRole('heading',{name:'用户的 HTML 标题'})).toBeVisible();
  await expect(markdown.getByAltText('课程封面')).toHaveAttribute('src','https://raw.githubusercontent.com/Lordog/dive-into-llms/f84c04268794ef94f8949808bbc14ab8636763a0/pics/icon/title.jpg');
  await expect(markdown.getByAltText('课程封面')).toHaveAttribute('width','48%');
  await expect(markdown.getByAltText('课程封面')).toHaveCSS('display','inline-block');
  expect((await markdown.getByRole('checkbox').boundingBox()).width).toBeLessThan(24);
  await expect(markdown.locator('table')).toContainText('42');
  await expect(markdown.locator('.katex')).toBeVisible();
  await expect(markdown.locator('script,iframe')).toHaveCount(0);
  expect(await page.evaluate(()=>window.__unsafe)).toBeUndefined();
  await expect(markdown.locator('a').filter({hasText:'Unsafe link'})).not.toHaveAttribute('href',/javascript:/);
  await markdown.getByRole('link',{name:'Jump to section'}).click();
  await expect(page).toHaveURL(/#user-content-section$/);
  await page.getByRole('combobox',{name:'界面语言'}).selectOption('en');
  await expect(markdown.getByRole('heading',{name:'用户的 HTML 标题'})).toBeVisible();
  await page.getByRole('button',{name:'Edit',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'Note body'})).toHaveValue(body);
  expect(writes).toBe(0);
});
