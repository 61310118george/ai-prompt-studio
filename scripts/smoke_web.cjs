// Run with bundled Node; opens an isolated browser profile and local fixture page.
const { createRequire } = require('node:module');
const { mkdirSync, writeFileSync } = require('node:fs');
const path = require('node:path');
const runtimeRequire = createRequire('/Users/baizijing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/runtime.cjs');
const { chromium } = runtimeRequire('playwright');

(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let promptReply = null;
  page.on('dialog', dialog => {
    const answer = dialog.type() === 'prompt' ? promptReply : undefined;
    promptReply = null;
    return dialog.accept(answer);
  });
  await page.goto('http://127.0.0.1:4173/web-preview/');
  await page.locator('#appVersion').filter({hasText:'V1.4'}).waitFor();
  await page.locator('#apiStatusText').filter({hasText:'未連結'}).waitFor();
  await page.locator('#promptProject').filter({hasText:'目前專案'}).waitFor();
  promptReply = '驗收群組';
  await page.click('#promptGroupAdd');
  await page.locator('.template-group').filter({hasText:'驗收群組'}).waitFor();
  await page.fill('#promptTitle','驗收：中文提示詞');
  await page.fill('#promptCategory','研究');
  await page.fill('#promptTags','驗收,中文');
  await page.fill('#promptContent','## 任務\n\n請整理研究資料。\n\n\n- 必須保留日期與數字。\n- 必須保留日期與數字。\n\n## 輸出格式\n條列');
  await page.click('#promptSave');
  await page.locator('#promptVersion').filter({hasText:'v1'}).waitFor();
  await page.locator('summary').filter({hasText:'進階：整理重複文字'}).click();
  await page.check('#promptDeduplicate');
  await page.click('#promptAnalyze');
  await page.locator('#promptMetrics').filter({hasText:'browser-heuristic'}).waitFor();
  if (await page.locator('#promptUseCandidate').isDisabled()) throw Error('Expected editable candidate');
  await page.click('#promptUseCandidate');
  await page.click('#promptSave');
  await page.locator('#promptVersion').filter({hasText:'v2'}).waitFor();
  await page.locator('[data-prompt-id]').dragTo(page.locator('.template-group').filter({hasText:'驗收群組'}));
  await page.locator('.template-group').filter({hasText:'驗收群組'}).locator('[data-prompt-id]').waitFor();
  await page.fill('#promptSearch','不存在的字詞');
  await page.locator('#templateGroups .template-card').count().then(count=>{if(count!==0)throw Error('Search should hide every template');});
  await page.fill('#promptSearch','驗收');
  await page.locator('[data-prompt-id]').waitFor();
  await page.click('#promptAnalyze');
  await page.locator('#promptMetrics').filter({hasText:'browser-heuristic'}).waitFor();
  await page.evaluate(()=>window.scrollTo(0,0));
  const output = path.join(__dirname,'..','docs','evidence');
  mkdirSync(output,{recursive:true});
  await page.screenshot({path:path.join(output,'prompt-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(output,'prompt-mobile.png'),fullPage:true});
  const dimensions = await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
  if(dimensions.scroll > dimensions.width + 1) throw Error(`Horizontal overflow ${JSON.stringify(dimensions)}`);
  await page.reload();
  await page.locator('[data-prompt-id]').waitFor();
  await page.click('[data-prompt-id]');
  await page.locator('#promptVersion').filter({hasText:'v2'}).waitFor();
  if(errors.length) throw Error(errors.join('\n'));
  const result = {passed:true,mode:'browser mock',workflow:'create group with delete control, save v1, analyze, apply candidate to draft, save v2, drag template, search, reload persistence',viewports:[1440,390],errors};
  writeFileSync(path.join(output,'web-smoke.json'),JSON.stringify(result,null,2));
  await page.setViewportSize({width:1200,height:1000});
  await page.goto('http://127.0.0.1:4173/deliverables/' + encodeURIComponent('專題企劃書.html'));
  if(await page.locator('h2').count() < 10) throw Error('Incomplete proposal');
  await page.locator('img').first().waitFor();
  if (!await page.locator('img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0))) {
    throw Error('Proposal image failed to load');
  }
  await page.screenshot({path:path.join(output,'proposal-preview.png')});
  await page.goto('http://127.0.0.1:4173/deliverables/' + encodeURIComponent('軟體規格書.html'));
  if(await page.locator('table').count() < 3) throw Error('Incomplete spec');
  await page.locator('img').first().waitFor();
  if (!await page.locator('img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0))) {
    throw Error('Specification image failed to load');
  }
  await page.screenshot({path:path.join(output,'spec-preview.png')});
  console.log(JSON.stringify(result));
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
