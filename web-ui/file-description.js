// Deterministic labels, not AI summaries; unknown documents expose their heading.
const PURPOSES = {
  'readme':'專案介紹、安裝方式與使用入口',
  'agents':'AI 協作規則、修改限制與驗收方式',
  'agents.override':'此目錄優先採用的 AI 協作規則',
  'claude':'Claude Code 的專案指令與協作規則',
  'claude.local':'此電腦使用的 Claude 個人專案指令',
  'gemini':'Gemini 的專案背景與工作規則',
  'memory':'長期偏好、穩定事實與經驗紀錄',
  'soul':'AI 角色個性、互動風格與行為原則',
  'user':'使用者背景與互動偏好',
  'tools':'工具設定、使用方式與環境備註',
  'identity':'AI 的名稱、角色與身分設定',
  'heartbeat':'定期檢查項目與提醒規則',
  'app-information-architecture':'頁面分區、導航與操作流程',
  'app-introduction':'App 用途、主要功能與使用情境',
  'codex-config-template':'Codex 專案設定的範例與用法',
  'database-schema':'資料表、欄位與資料關係',
  'project-brief':'專案目標、背景與目前範圍',
  'requirements':'功能需求、限制與驗收條件',
  'spec':'功能規格、技術設計與驗收方式',
  'decisions':'重要決策、選擇理由與取捨',
  'risks':'已知風險、限制與因應方式',
  'next-actions':'下一步工作與待辦事項',
  'memory-categories':'記憶分類、用途與整理方式',
  'ui-ux-design-system':'介面配色、字體與元件規範',
  'ui-ux-reference':'介面設計參考與採用原則',
  'web-ui':'桌面 App 內嵌介面與互動邏輯',
  'changelog':'版本更新與功能變更紀錄',
  'contributing':'參與開發與提交變更的規則',
  'license':'授權條款與使用限制',
};
export function fileDescription(file) {
  const name=file.relative_path.split('/').pop().replace(/\.md$/i,'').toLowerCase();
  const title=String(file.title||'').replace(/\s+/g,' ').trim();
  let description,source;
  if(name==='skill') {
    description=title?`技能：${title}`:'特定任務的適用情境、步驟與驗證';source=title?'文件標題':'檔案類型';
  } else if(PURPOSES[name]) {description=PURPOSES[name];source='依檔名的用途提示';}
  else if(file.classifications?.[0]?.purpose) {description=file.classifications[0].purpose;source='Agent 規格';}
  else {description=title?`主題：${title}`:'一般 Markdown 文件；查看內容確認用途';source=title?'文件標題':'未判定用途';}
  return {text:description.length>52?description.slice(0,51)+'…':description,source};
}
