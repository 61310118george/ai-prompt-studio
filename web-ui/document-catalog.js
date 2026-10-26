export const DOCUMENT_TYPES = {core:'核心文件', memory:'AI 記憶', skill:'技能 Skill', project:'專案'};
export const TOPICS = {
  '開發程式':['寫網頁','開發遊戲','開發 app'],
  '撰寫企劃':['撰寫文案','專案企劃'],
  '推廣行銷':['撰寫文案','分析市場','行銷顧問'],
  '其他':[],
};

// Topic IDs include their parent: planning copy and marketing copy are different tasks.
export const TOPIC_GUIDANCE = {
  '開發程式/寫網頁':'網站使用者、主要頁面、操作流程、裝置尺寸、現有技術與驗收方式',
  '開發程式/開發遊戲':'目標玩家、遊戲平台、核心玩法、操作、勝負條件與效能限制',
  '開發程式/開發 app':'使用者情境、主要流程、作業系統、資料儲存、權限與離線需求',
  '撰寫企劃/撰寫文案':'文件讀者、溝通目的、已確認素材、段落結構、語氣與篇幅',
  '撰寫企劃/專案企劃':'問題、目標、範圍、交付物、時程、預算、風險與驗收指標',
  '推廣行銷/撰寫文案':'品牌、受眾、發布平台、已確認賣點、行動呼籲與禁止宣稱',
  '推廣行銷/分析市場':'研究問題、地區、期間、受眾、競爭對象、來源與證據限制',
  '推廣行銷/行銷顧問':'商業目標、現況數據、渠道、預算、可用資源與成效衡量',
};
export const DOCUMENT_FIELDS = {
  core:[
    {id:'purpose',label:'專案目標與範圍',question:'希望 AI 協助完成什麼？哪些工作不在這次範圍？'},
    {id:'rules',label:'固定規則與禁止事項',question:'每次工作都必須遵守什麼？哪些修改或宣稱不能做？'},
    {id:'workflow',label:'協作與確認流程',question:'AI 應先做什麼？遇到資料不足或重大變更時要如何確認？'},
    {id:'verification',label:'完成與驗收方式',question:'你會用哪些結果、測試或數據判斷工作完成？'},
  ],
  memory:[
    {id:'background',label:'背景與已確認事實',question:'有哪些真實背景、產品或服務資訊需要 AI 記住？'},
    {id:'audience',label:'使用對象與需求',question:'服務誰？他們目前遇到什麼問題或需求？'},
    {id:'preferences',label:'語氣與工作偏好',question:'喜歡什麼語氣、篇幅、格式或工作方式？'},
    {id:'decisions',label:'既有決策與待確認事項',question:'哪些事情已決定？哪些仍未知、不能當成事實？'},
  ],
  skill:[
    {id:'trigger',label:'用途與使用時機',question:'這項技能負責什麼？什麼情況該用、什麼情況不該用？'},
    {id:'inputs',label:'需要提供的資料',question:'執行前需要使用者提供哪些資料？缺少時如何處理？'},
    {id:'steps',label:'執行步驟',question:'請描述從開始到完成的步驟，以及需要停下來確認的地方。'},
    {id:'output',label:'輸出格式與驗收',question:'最終交付什麼格式？如何檢查是否符合要求？'},
  ],
};

export function topicContext(major, minors) {
  return minors.map(minor=>TOPIC_GUIDANCE[`${major}/${minor}`]).filter(Boolean).join('；');
}

export function compileDocument(type, title, fields, tags, skillName='project-workflow') {
  const schema = DOCUMENT_FIELDS[type];
  if(!schema)throw Error('請先選擇文件類型。');
  if(!title.trim())throw Error('請先填寫標題。');
  if(!schema.some(field=>fields[field.id]?.trim()))throw Error('請至少填寫一個內容欄位，或使用右側 AI 協助撰寫。');
  let prefix='';
  if(type==='skill') {
    if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(skillName)||skillName.length>64)throw Error('技能識別名稱限 1–64 字的小寫英數與單一連字號。');
    if(/^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/.test(skillName))throw Error('技能識別名稱不可使用 Windows 保留名稱。');
    if(!fields.trigger?.trim()||!fields.steps?.trim())throw Error('技能必須填寫「用途與使用時機」及「執行步驟」。');
    if(fields.trigger.trim().length>1024)throw Error('技能用途與使用時機請保持在 1,024 字以內。');
    prefix=`---\nname: ${JSON.stringify(skillName)}\ndescription: ${JSON.stringify(fields.trigger.trim())}\n---\n\n`;
  }
  const sections=schema.filter(field=>fields[field.id]?.trim()).map(field=>`## ${field.label}\n\n${fields[field.id].trim()}`);
  return `${prefix}# ${title.trim()}\n\n${tags?`用途：${tags}\n\n`:''}${sections.join('\n\n')}\n`;
}
