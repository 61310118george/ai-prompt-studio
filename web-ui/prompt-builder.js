const BASE_TEMPLATE = {
  tag: '一般',
  role: '任務助理',
  task: '釐清目標並完成指定任務',
  requirements: '資訊不足時先列出待確認事項|保留使用者提供的事實、數字與限制|不要捏造未提供的內容',
  output: '先給結論再列出重點與下一步',
  acceptance: '輸出符合指定格式|重要限制都有保留|不確定處已清楚標示',
};

export const DEFAULT_PROMPT_TAG_TEMPLATES = [
  BASE_TEMPLATE,
  {tag:'寫作',role:'文字編輯',task:'依讀者與目的完成文字內容',requirements:'使用自然且清楚的繁體中文',output:'可直接使用的完整文字',acceptance:'語氣一致|段落容易閱讀'},
  {tag:'生成文檔',role:'技術文件撰寫者',task:'建立結構完整且可維護的文件',requirements:'使用 Markdown 標題層級|補上範例與限制',output:'Markdown 文件',acceptance:'章節完整|標題層級正確'},
  {tag:'驗收',role:'品質驗收人員',task:'逐項比對需求與成果',requirements:'沒有證據時標示未驗證',output:'需求、結果、證據、缺口與下一步',acceptance:'每項需求都有結論'},
  {tag:'製作',role:'內容製作人',task:'依目標完成可交付成品',requirements:'先確認尺寸、格式與限制',output:'成品與製作說明',acceptance:'符合交付格式|可直接使用'},
  {tag:'開發',role:'軟體工程師',task:'實作指定功能並維持既有行為',requirements:'先閱讀現有程式|遵循專案慣例|補上必要測試',output:'修改內容、測試結果與注意事項',acceptance:'需求可重現|測試通過'},
  {tag:'除錯',role:'問題診斷工程師',task:'找出問題原因與最小修正方式',requirements:'先重現再修改|區分證據與推測',output:'原因、驗證方式、修正與風險',acceptance:'問題可重現|修正後不再發生'},
  {tag:'研究',role:'研究助理',task:'整理資料並回答研究問題',requirements:'區分來源事實與推論|保留來源',output:'結論、證據、限制與待查問題',acceptance:'重要主張有依據'},
];

function parseCsv(text) {
  const rows = [];
  let row = [], cell = '', quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index], next = text[index + 1];
    if (char === '"' && quoted && next === '"') { cell += '"'; index += 1; }
    else if (char === '"') quoted = !quoted;
    else if (char === ',' && !quoted) { row.push(cell); cell = ''; }
    else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && next === '\n') index += 1;
      row.push(cell); cell = '';
      if (row.some(value => value.trim())) rows.push(row);
      row = [];
    } else cell += char;
  }
  row.push(cell);
  if (row.some(value => value.trim())) rows.push(row);
  return rows;
}

export function parsePromptTemplateCatalog(text) {
  const [headers = [], ...rows] = parseCsv(String(text || '').replace(/^\uFEFF/, ''));
  const keys = headers.map(value => value.trim());
  if (!keys.includes('tag')) throw Error('CSV 必須包含 tag 欄位。');
  return rows.map(row => Object.fromEntries(keys.map((key, index) => [key, String(row[index] || '').trim()])))
    .filter(item => item.tag);
}

export async function loadPromptTemplateCatalog() {
  try {
    const response = await fetch(new URL('./data/prompt-template-catalog.csv', import.meta.url));
    if (!response.ok) throw Error(`HTTP ${response.status}`);
    const catalog = parsePromptTemplateCatalog(await response.text());
    return catalog.length ? catalog : DEFAULT_PROMPT_TAG_TEMPLATES;
  } catch {
    return DEFAULT_PROMPT_TAG_TEMPLATES;
  }
}

const splitItems = value => String(value || '').split('|').map(item => item.trim()).filter(Boolean);
const unique = values => [...new Set(values.filter(Boolean))];

export function buildPromptFromTags(title, selectedTags, catalog) {
  const tags = unique(selectedTags);
  const selected = catalog.filter(item => tags.includes(item.tag));
  const templates = selected.length ? selected : [catalog.find(item => item.tag === '一般') || BASE_TEMPLATE];
  const roles = unique(templates.map(item => item.role));
  const tasks = unique(templates.map(item => item.task));
  const requirements = unique(templates.flatMap(item => splitItems(item.requirements)));
  const outputs = unique(templates.flatMap(item => splitItems(item.output)));
  const acceptance = unique(templates.flatMap(item => splitItems(item.acceptance)));
  const bullets = items => items.map(item => `- ${item}`).join('\n');
  const tagLine = tags.length ? `\n\n使用標籤：${tags.join('、')}` : '';
  return `# ${title.trim()}\n\n## 角色\n\n${roles.join('、')}\n\n## 任務\n\n${tasks.join('；')}。\n\n處理主題：${title.trim()}${tagLine}\n\n## 輸入資料\n\n[請貼上本次任務需要的資料；沒有資料時請先說明。]\n\n## 執行要求\n\n${bullets(requirements)}\n\n## 輸出格式\n\n${bullets(outputs)}\n\n## 驗收標準\n\n${bullets(acceptance)}\n`;
}

export function parseMarkdownSections(markdown) {
  const lines = String(markdown || '').replace(/\r\n?/g, '\n').split('\n');
  const headings = [];
  lines.forEach((line, index) => {
    const match = line.match(/^(#{1,6})\s+(.+?)\s*$/);
    if (match) headings.push({headingLine:index, level:match[1].length, title:match[2]});
  });
  if (!headings.length) return [{headingLine:-1, bodyStart:0, endLine:lines.length, level:0, title:'全文', body:lines.join('\n')}];
  const sections = [];
  if (headings[0].headingLine > 0) {
    sections.push({headingLine:-1, bodyStart:0, endLine:headings[0].headingLine, level:0, title:'文件開頭', body:lines.slice(0, headings[0].headingLine).join('\n').trimEnd()});
  }
  headings.forEach((heading, index) => {
    const endLine = headings[index + 1]?.headingLine ?? lines.length;
    sections.push({...heading, bodyStart:heading.headingLine + 1, endLine, body:lines.slice(heading.headingLine + 1, endLine).join('\n').replace(/^\n/, '').replace(/\n$/, '')});
  });
  return sections;
}

export function updateMarkdownSection(markdown, sectionIndex, changes) {
  const normalized = String(markdown || '').replace(/\r\n?/g, '\n');
  const lines = normalized.split('\n');
  const sections = parseMarkdownSections(normalized);
  const section = sections[Number(sectionIndex)];
  if (!section) throw Error('找不到要更新的 Markdown 項目。');
  const body = String(changes.body || '').replace(/\r\n?/g, '\n').replace(/^\n+|\n+$/g, '');
  if (section.level === 0) {
    lines.splice(section.bodyStart, section.endLine - section.bodyStart, ...body.split('\n'));
  } else {
    const level = Math.min(6, Math.max(1, Number(changes.level) || section.level));
    const title = String(changes.title || '').trim();
    if (!title) throw Error('項目標題不能空白。');
    const replacement = [`${'#'.repeat(level)} ${title}`, ''];
    if (body) replacement.push(...body.split('\n'));
    lines.splice(section.headingLine, section.endLine - section.headingLine, ...replacement);
  }
  return `${lines.join('\n').replace(/\n+$/, '')}\n`;
}

const escapeHtml = value => String(value).replace(/[&<>]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[char]));

function highlightMarkdown(value) {
  let fenced = false;
  return String(value).split('\n').map(line => {
    const escaped = escapeHtml(line);
    if (/^\s*```/.test(line)) { fenced = !fenced; return `<span class="md-code-fence">${escaped}</span>`; }
    if (fenced) return `<span class="md-code-line">${escaped}</span>`;
    const heading = line.match(/^(#{1,6})(\s+)(.*)$/);
    if (heading) return `<span class="md-heading md-heading-${heading[1].length}"><span class="md-marker">${heading[1]}</span>${escapeHtml(heading[2] + heading[3])}</span>`;
    if (/^\s*[-*+]\s+/.test(line)) return `<span class="md-list-line">${escaped}</span>`;
    if (/^\s*>/.test(line)) return `<span class="md-quote-line">${escaped}</span>`;
    return escaped;
  }).join('\n');
}

export function mountMarkdownEditor(editor, onInput) {
  let value = '';
  const selectionOffset = () => {
    const selection = document.getSelection();
    if (!selection?.rangeCount || !editor.contains(selection.anchorNode)) return null;
    const range = selection.getRangeAt(0).cloneRange();
    range.selectNodeContents(editor);
    range.setEnd(selection.anchorNode, selection.anchorOffset);
    return range.toString().length;
  };
  const restoreSelection = offset => {
    if (offset === null) return;
    const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    let remaining = offset, node;
    while ((node = walker.nextNode())) {
      if (remaining <= node.data.length) {
        const range = document.createRange();
        range.setStart(node, remaining); range.collapse(true);
        const selection = document.getSelection(); selection.removeAllRanges(); selection.addRange(range);
        return;
      }
      remaining -= node.data.length;
    }
    const range = document.createRange(); range.selectNodeContents(editor); range.collapse(false);
    const selection = document.getSelection(); selection.removeAllRanges(); selection.addRange(range);
  };
  const render = (next, offset = null) => {
    value = String(next || '').replace(/\r\n?/g, '\n');
    editor.innerHTML = highlightMarkdown(value);
    editor.classList.toggle('is-empty', !value);
    if (offset !== null) restoreSelection(Math.min(offset, value.length));
  };
  Object.defineProperty(editor, 'value', {configurable:true, get:()=>value, set:next=>render(next)});
  editor.addEventListener('input', () => {
    const offset = selectionOffset();
    value = editor.innerText.replace(/\u00a0/g, ' ').replace(/\r\n?/g, '\n');
    render(value, offset);
    onInput?.(value);
  });
  render('');
  return {getValue:()=>value, setValue:next=>render(next)};
}
