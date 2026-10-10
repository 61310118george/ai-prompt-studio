// Offline guidance. Thresholds are product heuristics, never subscription quotas.
export const USAGE_SOURCES = [
  ['Codex 模型', 'https://learn.chatgpt.com/docs/models'],
  ['Codex 方案', 'https://learn.chatgpt.com/docs/pricing'],
  ['Claude 用量', 'https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan'],
];
export function usageAdvice({tool, content = '', files = []}) {
  const bytes = files.reduce((sum, f) => sum + Number(f.size || 0), 0);
  const promptTokens = Math.ceil([...content].reduce((sum, c) => sum + (c.codePointAt(0) > 127 ? 1 : .25), 0));
  const level = promptTokens < 500 ? 0 : promptTokens < 2000 ? 1 : promptTokens < 8000 ? 2 : 3;
  const complex = /重構|架構|遷移|跨.*模組|refactor|architecture|migration/i.test(content);
  const simple = /改名|錯字|格式|摘要|rename|typo|format|summari/i.test(content);
  const model = tool === 'claude' ? (complex ? 'Opus 規劃、Sonnet 執行' : simple ? 'Haiku 處理明確的小任務' : 'Sonnet 處理一般開發') : (complex ? 'Astra 處理困難規劃；Sol 執行日常修改' : simple ? 'Luna 處理明確的小任務' : 'Sol 處理一般開發');
  return {level, label:['最低','偏低','偏高','最高'][level], units:promptTokens, promptTokens, model,
    plan: tool === 'claude' ? '一般個人使用先評估 Pro；持續遇到上限時再比較 Max。以帳號實際用量及預算決定。' : '一般個人使用先評估 Plus；持續遇到上限時再比較 Pro。以帳號實際用量及預算決定。',
    reason:`目前提示詞粗估約 ${promptTokens.toLocaleString()} Token。專案另有 ${files.length} 份 Markdown（${Math.round(bytes / 1024)} KB），只有實際附加或由工具載入時才會增加上下文。`,
    note:'這是上下文負擔，不能預測完成專案的總用量或重置時間。App 未連接帳號額度；大型文件也不一定每次全部載入。'};
}
export function mountUsageGuide(root, state, content) {
  root.innerHTML = `<div class="usage-top"><label>預計使用的工具<select id="usageTool"><option value="codex">Codex（雲端）</option><option value="claude">Claude Code（雲端）</option><option value="local">本機模型</option></select></label><div class="usage-burden"><small>上下文負擔</small><strong id="usageLevel" role="status"></strong><span id="usageEstimate"></span></div></div><p id="usageModel"></p><details><summary>節省額度與方案參考</summary><p id="usageReason"></p><p id="usagePlan"></p><p id="usageNote"></p><ul><li>每次只提供當前任務需要的檔案。</li><li>先確認修改範圍與驗收方式，减少來回重做。</li><li>階段完成後整理交接摘要；新任務開新對話。</li><li>重置時間與剩餘額度請查看官方帳號用量頁。</li></ul><p>規格查證：2026-10-07。模型版本及可用性以帳號選單為準。</p><p>${USAGE_SOURCES.map(([name,url])=>`<a href="${url}" target="_blank" rel="noreferrer">${name}</a>`).join(' · ')}</p></details>`;
  const update = () => {
    const tool = root.querySelector('select').value;
    const advice = usageAdvice({tool, content:content(), files:state.scan?.files || []});
    const local = tool === 'local';
    const level = root.querySelector('#usageLevel');
    level.textContent = local ? '不適用雲端額度' : advice.label;
    level.className = `usage-level level-${local ? 0 : advice.level}`;
    const estimate = root.querySelector('#usageEstimate');
    estimate.textContent = `目前提示詞約 ${advice.promptTokens.toLocaleString()} Token`;
    estimate.dataset.tokens = String(advice.promptTokens);
    const model = root.querySelector('#usageModel');
    model.textContent = local ? '本機推論不扣雲端月費額度，仍受記憶體與上下文長度限制。' : `模型建議：${advice.model}。`;
    model.dataset.model = advice.model;
    for (const [id, value] of [['usageReason',advice.reason],['usagePlan',local ? '本機模型無需購買雲端用量方案。' : advice.plan],['usageNote',advice.note]]) root.querySelector(`#${id}`).textContent = value;
  };
  root.querySelector('select').addEventListener('change',update);
  update(); return update;
}
