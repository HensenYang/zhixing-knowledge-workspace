// Single-process fallback for hosts where the Playwright CLI worker cannot start.
// Runs the actual spec functions with Playwright's browser and expect assertions.
// Fixtures supported here: page, context, browser, and beforeEach.
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const projectRequire = createRequire(path.join(root, 'frontend_Web/package.json'));
const {chromium} = projectRequire('playwright');
const {expect} = projectRequire('@playwright/test');
const baseURL = process.env.WORKSPACE_TEST_URL;
if (!baseURL || process.env.WORKSPACE_DISPOSABLE_TEST !== '1') {
  throw Error('Run through verify_full.py against its disposable database.');
}
const output = process.env.WORKSPACE_TEST_REPORT_DIR;
fs.mkdirSync(output, {recursive:true});
const cases = [];
const files = process.argv.slice(2);
for (const file of files.length ? files : fs.readdirSync(path.join(root, 'frontend_Web/tests')).filter(name=>name.endsWith('.spec.js')).sort()) {
  const hooks = [];
  function test(name, body) { cases.push({file,name,body,hooks:[...hooks]}); }
  test.beforeEach = fn => hooks.push(fn);
  // The fallback uses a 90-second ceiling for each scenario, including its hooks.
  test.setTimeout = () => {};
  const raw = fs.readFileSync(path.join(root, 'frontend_Web/tests', file), 'utf8');
  const source = raw.replace(/^import\s+.*\s+from\s+['"][^'"]+['"];?\s*$/gm, '');
  new Function('test','expect','fs','path',source)(test,expect,
    raw.includes("'node:fs/promises'") ? fs.promises : fs,path);
}
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true,timeout:20000});
  const results = [];
  try {
    for (const item of cases) {
      const started = Date.now();
      const context = await browser.newContext({baseURL,viewport:{width:1440,height:1000}});
      const page = await context.newPage();
      const pageErrors=[];
      page.on('pageerror',error=>pageErrors.push(error.message));
      page.setDefaultTimeout(12000);
      const testInfo = {workerIndex:0,repeatEachIndex:0};
      let timer;
      try {
        await Promise.race([(async () => {
          for (const hook of item.hooks) await hook({page,context,browser},testInfo);
          await item.body({page,context,browser},testInfo);
          expect(pageErrors).toEqual([]);
        })(), new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Scenario exceeded 90 seconds')),90000);})]);
        results.push({file:item.file,name:item.name,status:'passed',milliseconds:Date.now()-started});
        console.log('PASS '+item.file+' :: '+item.name);
      } catch (error) {
        const screenshot=path.join(output,'failure-'+results.length+'.png');
        await page.screenshot({path:screenshot,fullPage:true}).catch(()=>{});
        results.push({file:item.file,name:item.name,status:'failed',milliseconds:Date.now()-started,error:error.stack,screenshot});
        console.error('FAIL '+item.file+' :: '+item.name+'\n'+error.stack);
      } finally { clearTimeout(timer); await context.close(); }
      fs.writeFileSync(path.join(output,'browser-fallback.json'),JSON.stringify(results,null,2));
    }
  } finally { await browser.close(); }
  const failures=results.filter(item=>item.status==='failed').length;
  console.log((results.length-failures)+'/'+results.length+' browser scenarios passed');
  process.exitCode=failures?1:0;
})().catch(error=>{console.error(error);process.exitCode=1;});
