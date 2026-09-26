// Capture the real shared Web UI with browser-safe fixture data for project documents.
const { createRequire } = require('node:module');
const { mkdirSync } = require('node:fs');
const path = require('node:path');
const runtimeRequire = createRequire('/Users/baizijing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/runtime.cjs');
const { chromium } = runtimeRequire('playwright');

(async () => {
  const output = path.join(__dirname, '..', 'docs', 'evidence', 'interfaces');
  mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 1 });
  page.on('dialog', dialog => dialog.accept());
  await page.goto('http://127.0.0.1:4173/web-preview/');
  await page.locator('#runtimeLabel').filter({ hasText: '瀏覽器' }).waitFor();
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.locator('#promptProject').filter({ hasText: '目前專案' }).waitFor();

  await page.fill('#promptTitle', '研究資料整理提示詞');
  await page.fill('#promptCategory', '專題研究');
  await page.fill('#promptTags', '研究,摘要,繁體中文');
  await page.fill('#promptContent', '## 任務\n\n請整理訪談逐字稿，保留日期、數字與受訪者原意。\n\n\n- 使用繁體中文。\n- 不要加入逐字稿沒有提到的結論。\n- 不要加入逐字稿沒有提到的結論。\n\n## 輸出格式\n\n用三點摘要與待確認問題呈現。');
  await page.fill('#promptPrice', '2.5');
  await page.fill('#promptCalls', '1000');
  await page.check('#promptDeduplicate');
  await page.click('#promptAnalyze');
  await page.locator('#promptMetrics').filter({ hasText: '原文 Token' }).waitFor();
  await page.screenshot({ path: path.join(output, '01-prompt-workbench.png') });

  await page.click('[data-page="projects"]');
  await page.click('[data-preview-file="AGENTS.md"]');
  await page.waitForTimeout(600);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, '02-project-map.png') });

  await page.click('[data-page="programming"]');
  await page.fill('#field-purpose', '整理與管理不同 AI 專案的提示詞及記憶檔案。');
  await page.fill('#field-goals', '讓使用者快速找到提示詞\n比較精簡前後 Token\n安全寫回 Markdown');
  await page.fill('#field-non_goals', '不使用雲端模型自動改寫\n不保證所有精簡結果都能改善回答');
  await page.click('#compileButton');
  await page.locator('#compilerStatus').filter({ hasText: '本機編譯完成' }).waitFor();
  await page.waitForTimeout(600);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, '03-memory-programming.png') });

  await page.click('[data-page="health"]');
  await page.click('#runHealthButton');
  await page.locator('#effectiveFiles code').waitFor();
  await page.waitForTimeout(600);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, '04-memory-health.png') });

  await page.click('[data-page="settings"]');
  await page.waitForTimeout(600);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, '05-settings-sources.png') });
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
