import { mountUsageGuide } from './usage-guide.js';
import { PROMPT_TEMPLATES } from './prompt-templates.js';
import { mountCloudAnalysis } from './cloud-analysis.js';
export function mountPromptWorkspace({ bridge, state, escapeHtml: esc, reportError, toast }) {
  const root = document.querySelector('#page-prompts');
  root.innerHTML = `
    <div class="page-intro"><div><h2>提示詞工作台</h2><p>套用範本或自行撰寫；儲存後會直接進入範本庫，可依群組拖曳整理。</p></div><span class="agent-chip">預設離線 · AI 分析需確認</span></div>
    <p id="promptProject" class="source-note">先選擇專案資料夾，或直接在右側草稿試寫與分析。</p>
    <div class="prompt-layout">
      <section class="panel prompt-library"><div class="panel-heading"><h3>提示詞範本庫</h3></div><div class="prompt-library-body">
        <section class="library-block library-create"><div class="library-section-heading"><h4>建立新提示詞</h4><p>從空白草稿開始。儲存後會直接加入下方範本庫。</p></div><button class="button secondary" id="promptNew" title="開始新草稿，按儲存版本後加入範本庫">建立空白提示詞</button></section>
        <section class="library-block template-library"><div class="library-section-heading library-title-row"><div><h4>範本庫</h4><p>內建範本可帶入後改標題；自己儲存的範本可拖到任一群組。</p></div><button class="button secondary compact-button" id="promptGroupAdd">新增群組</button></div>
        <label class="template-search">搜尋範本<input id="promptSearch" type="search" placeholder="例如：客服、JSON、摘要"></label>
        <div id="templateGroups" class="template-groups"></div></section>
      </div>
      </section>
      <section class="panel"><div class="panel-heading"><h3>提示詞編輯</h3><span id="promptVersion" class="count">草稿</span></div>
        <div class="prompt-fields"><label>標題<input id="promptTitle" maxlength="200" placeholder="例如：產品需求審查"></label>
        <div class="prompt-pair"><label>群組<input id="promptCategory" list="promptGroupOptions" value="一般" placeholder="選擇或輸入群組"><datalist id="promptGroupOptions"></datalist></label><label>標籤（逗號分隔）<input id="promptTags" placeholder="開發,需求"></label></div>
        <details><summary>從引導模板建立提示詞</summary><div class="prompt-fields">
          <label>情境<select id="promptScenario"><option value="general">一般任務</option><option value="review">程式審查</option><option value="writing">文字整理</option><option value="research">研究筆記</option></select></label>
          <label>角色<input id="builderRole" placeholder="你希望 AI 扮演的角色"></label>
          <label>任務<textarea id="builderTask" placeholder="要完成什麼？成功標準是什麼？"></textarea></label>
          <label>背景／輸入<textarea id="builderContext" placeholder="只填本次任務需要的資訊"></textarea></label>
          <label>限制<textarea id="builderConstraints" placeholder="必須保留、不能改變的條件"></textarea></label>
          <label>輸出格式<input id="builderFormat" placeholder="例如：表格、JSON、三點摘要"></label>
          <button class="button secondary" id="promptBuild">產生草稿</button></div></details>
        <label>提示詞內容<textarea id="promptContent" class="prompt-editor" spellcheck="false" placeholder="貼上既有提示詞，或展開引導模板建立內容。"></textarea></label>
        <div class="inline-actions prompt-actions"><button class="button primary" id="promptSave">儲存版本</button><button class="button secondary" id="promptCopy">複製</button><button class="button secondary" id="promptArchive">封存</button></div>
        <details><summary>本機 Markdown 匯入／匯出</summary><div class="prompt-fields">
          <label>從目前專案匯入<select id="promptImportPath"><option value="">選擇 Markdown</option></select></label><button class="button secondary" id="promptImport">匯入為草稿</button>
          <label>匯出相對路徑<input id="promptExportPath" value="prompts/my-prompt.md"></label>
          <button class="button secondary" id="promptExportPreview">預覽檔案變更</button><pre class="code-view" id="promptExportDiff">尚未預覽。</pre>
          <button class="button primary" id="promptExportApply" disabled>套用匯出</button>
          <button class="button secondary" id="promptRestoreExport" disabled>復原這次匯出</button>
        </div></details>
        <details><summary>版本歷史（選取後可另存新版本）</summary><div id="promptVersions" class="selection-list"></div></details>
      </div></section>
      <details class="panel prompt-cleanup"><summary>進階：整理重複文字</summary><div class="prompt-fields">
        <label class="check-label"><input id="promptDeduplicate" type="checkbox">提出移除相鄰重複條列的候選</label>
        <button class="button primary" id="promptAnalyze">分析並產生精簡候選</button>
        <div id="promptMetrics" class="prompt-metrics"><p>比較整理前後的文字長度；候選內容請先確認再採用。</p></div>
        <div id="promptWarnings" class="source-note">少用 Token 不代表回答更好；精簡後請檢查必要條件與輸出品質。</div>
        <details open><summary>精簡候選</summary><pre class="code-view prompt-result" id="promptCandidate">尚無分析。</pre></details>
        <details><summary>內容差異與變更原因</summary><pre class="code-view" id="promptDiff"></pre><ul id="promptChanges"></ul></details>
        <button class="button secondary" id="promptUseCandidate" disabled>將候選帶回草稿</button>
        <button class="button secondary" id="promptReport" disabled>下載分析報告 JSON</button>
      </div></details>
    </div>`;
  const usage = document.createElement('div'); usage.className = 'usage-guide';
  root.querySelector('#promptContent').closest('label').before(usage);
  const updateUsage = mountUsageGuide(usage, state, () => root.querySelector('#promptContent').value);
  const updateCloud = mountCloudAnalysis({root:usage, bridge, content:()=>root.querySelector('#promptContent').value});
  root.querySelector('#promptVersions').closest('details').after(root.querySelector('.prompt-cleanup'));
  const $ = (id) => root.querySelector(`#${id}`);
  let current = null, analysis = null, exportPreview = null, lastExport = null, entries = [], groups = [], loadEpoch = 0;
  const mockKey = 'prompt-studio-library-v1', mockGroupsKey = 'prompt-studio-library-groups-v1';
  const mockLoad = () => { try { return JSON.parse(localStorage.getItem(mockKey) || '[]'); } catch { return []; } };
  const mockGroups = () => { try { return JSON.parse(localStorage.getItem(mockGroupsKey) || '[]'); } catch { return []; } };
  const response = (r) => { if (!r?.ok) throw Error(r?.error || '本機操作失敗'); return r.data; };
  const project = () => { if (!state.project) throw Error('請先到「專案」選擇資料夾。'); return state.project.path; };
  const run = (fn) => async () => { reportError(''); try { await fn(); } catch (error) { reportError(error.message); } };
  const dirty = () => {
    updateUsage();
    updateCloud();
    analysis = null; exportPreview = null;
    $('promptUseCandidate').disabled = true; $('promptReport').disabled = true; $('promptExportApply').disabled = true;
    $('promptMetrics').innerHTML = '<p>草稿或分析條件已變更，請重新分析。</p>';
    $('promptCandidate').textContent = '請重新分析目前草稿。';
    $('promptDiff').textContent = '';
    $('promptChanges').replaceChildren();
  };
  const values = () => ({ title: $('promptTitle').value, category: $('promptCategory').value, tags: $('promptTags').value, content: $('promptContent').value });
  const mayReplace = () => !Object.entries(values()).some(([key,value])=>value !== (current?.[key] || (key==='category'?'一般':''))) || window.confirm('目前有尚未儲存的草稿，確定換成另一份？');
  const defaultGroups = () => [...new Set(PROMPT_TEMPLATES.map(item => item.category).concat(['一般']))];
  const applyTemplate = async (index) => {
    if(!mayReplace())return;
    const template=PROMPT_TEMPLATES[Number(index)]; await select(null);
    for(const [key,id] of [['title','promptTitle'],['category','promptCategory'],['tags','promptTags'],['content','promptContent']])$(id).value=template[key];
    dirty();$('promptContent').focus();toast('範本已帶入草稿，可直接修改標題；儲存後會加入範本庫。');
  };
  async function history() {
    $('promptVersions').replaceChildren();
    if (!current) return;
    const revisions = bridge.runtime === 'desktop' ? response(await bridge.call('list_prompt_versions', project(), current.id)) : (current.revisions || []).slice().reverse();
    for (const revision of revisions) {
      const button = document.createElement('button'); button.className = 'selection-item';
      button.textContent = `v${revision.version} · ${revision.title} · ${revision.created_at || ''}`;
      button.addEventListener('click', () => { for (const [key, id] of [['title','promptTitle'],['content','promptContent'],['category','promptCategory'],['tags','promptTags']]) $(id).value = revision[key] || ''; dirty(); toast('歷史內容已帶回草稿，儲存後才會建立新版本。'); });
      $('promptVersions').append(button);
    }
  }
  async function select(item) {
    current = item;
    for (const [key, id] of [['title','promptTitle'],['content','promptContent'],['category','promptCategory'],['tags','promptTags']]) $(id).value = item?.[key] || (key === 'category' ? '一般' : '');
    $('promptVersion').textContent = item ? `v${item.version}` : '草稿';
    $('promptArchive').textContent = item?.archived ? '取消封存' : '封存';
    dirty(); await history();
  }
  function renderLibrary() {
    const query = $('promptSearch').value.trim().toLocaleLowerCase();
    const visible = entries.filter(item => !query || [item.title,item.content,item.category,item.tags].join(' ').toLocaleLowerCase().includes(query));
    const names = [...new Set(defaultGroups().concat(groups.map(group=>group.name), visible.map(item=>item.category)))];
    $('promptGroupOptions').innerHTML = names.map(name=>`<option value="${esc(name)}"></option>`).join('');
    const matchesTemplate = template => !query || [template.title,template.category,template.tags,template.content].join(' ').toLocaleLowerCase().includes(query);
    $('templateGroups').innerHTML = names.map(name => {
      const builtins = PROMPT_TEMPLATES.map((item,index)=>({item,index})).filter(({item})=>item.category===name && matchesTemplate(item));
      const saved = visible.filter(item=>item.category===name);
      const cards = [
        ...builtins.map(({item,index})=>`<button class="template-card builtin-template" data-template="${index}"><span class="template-card-title">${esc(item.title)}</span><small>內建範本 · 點選後可改標題</small></button>`),
        ...saved.map(item=>`<button class="template-card saved-template" draggable="true" data-prompt-id="${item.id}"><span class="template-card-title">${esc(item.title)}</span><small>${esc(item.tags || '我的範本')} · v${item.version}</small></button>`),
      ].join('') || '<p class="empty-state group-empty">把已儲存的範本拖到這裡。</p>';
      return `<section class="template-group" data-group-name="${esc(name)}"><header><strong>${esc(name)}</strong><span>${builtins.length + saved.length}</span></header><div class="template-group-items">${cards}</div></section>`;
    }).join('') || '<p class="empty-state">尚無範本。先選擇專案後儲存一份提示詞。</p>';
    $('templateGroups').querySelectorAll('[data-template]').forEach(button=>button.addEventListener('click',run(()=>applyTemplate(button.dataset.template))));
    $('templateGroups').querySelectorAll('[data-prompt-id]').forEach(button=>{
      button.addEventListener('click',run(()=>select(entries.find(item=>String(item.id)===button.dataset.promptId))));
      button.addEventListener('dragstart',event=>{event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',button.dataset.promptId);button.classList.add('dragging');});
      button.addEventListener('dragend',()=>button.classList.remove('dragging'));
    });
    $('templateGroups').querySelectorAll('[data-group-name]').forEach(group=>{
      group.addEventListener('dragover',event=>{event.preventDefault();event.dataTransfer.dropEffect='move';group.classList.add('drag-over');});
      group.addEventListener('dragleave',()=>group.classList.remove('drag-over'));
      group.addEventListener('drop',event=>run(async()=>{
        event.preventDefault();group.classList.remove('drag-over');
        const item = entries.find(entry=>String(entry.id)===event.dataTransfer.getData('text/plain'));
        const name = group.dataset.groupName;
        if(!item || item.category===name)return;
        if(bridge.runtime==='desktop') response(await bridge.call('move_prompt_to_group',project(),item.id,name));
        else { const data=mockLoad(), index=data.findIndex(entry=>String(entry.id)===String(item.id)); if(index>=0){data[index].category=name;localStorage.setItem(mockKey,JSON.stringify(data));} }
        toast(`已將「${item.title}」移到「${name}」。`);await reload();
      })());
    });
  }
  async function reload(reset = false) {
    updateUsage();
    const epoch = ++loadEpoch;
    $('promptProject').textContent = state.project ? `目前專案：${state.project.name} · ${state.project.path}` : '選擇專案後可保存；草稿分析可獨立使用。';
    if (reset) await select(null);
    $('promptImportPath').innerHTML = '<option value="">選擇 Markdown</option>' + (state.scan?.files || []).map(f => `<option value="${esc(f.relative_path)}">${esc(f.relative_path)}</option>`).join('');
    if (!state.project) { entries=[];groups=[];renderLibrary(); return; }
    const query = '', category = '', archived = false;
    let result;
    if (bridge.runtime === 'desktop') result = response(await bridge.call('list_prompts', project(), query, category, archived));
    else result = mockLoad().filter(p => p.project_path === project() && Boolean(p.archived) === archived && (!category || p.category === category) && [p.title,p.content,p.category,p.tags].join(' ').toLowerCase().includes(query.toLowerCase()));
    if (epoch !== loadEpoch) return;
    entries = result;
    groups = bridge.runtime === 'desktop' ? response(await bridge.call('list_prompt_groups', project())) : mockGroups().map(name=>({name}));
    if (epoch !== loadEpoch) return;
    renderLibrary();
  }
  async function save(archived = Boolean(current?.archived)) {
    const request = { ...values(), id: current?.id, version: current?.version, archived, project_path: project() };
    if (!request.title.trim() || !request.content.trim()) throw Error('請填寫標題與提示詞內容。');
    if (bridge.runtime === 'desktop') current = response(await bridge.call('save_prompt', request));
    else {
      const data = mockLoad(), index = data.findIndex(p => p.id === current?.id);
      current = {...request, id: current?.id || Date.now(), version: (current?.version || 0) + 1, created_at: new Date().toISOString(), revisions: [...(current?.revisions || [])]};
      current.revisions.push({...values(), version: current.version, created_at: current.created_at});
      if (index < 0) data.push(current); else data[index] = current;
      localStorage.setItem(mockKey, JSON.stringify(data));
    }
    $('promptVersion').textContent = `v${current.version}`; $('promptArchive').textContent = current.archived ? '取消封存' : '封存';
    await reload(); await history(); toast('已儲存提示詞版本。');
  }
  function mockAnalyze(request) {
    const text = request.content, output = [], changes = []; let fence = null, previous = '';
    for (const [index, line] of text.split(/(?<=\n)/).entries()) {
      const marker = line.match(/^ {0,3}(`{3,}|~{3,})/);
      if (fence) { output.push(line); if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length && !line.slice(marker[0].length).trim()) fence = null; previous = ''; continue; }
      if (marker) { fence = marker[1]; output.push(line); previous = ''; continue; }
      if (!line.trim() && output.length && !output.at(-1).trim()) { changes.push({line:index+1,detail:'移除連續多餘空白行'}); continue; }
      const bullet = /^[-*+] \S/.test(line) ? line.replace(/[\r\n]+$/, '') : '';
      if (request.remove_duplicates && bullet && bullet === previous) { changes.push({line:index+1,detail:'移除相鄰完全相同條列'}); continue; }
      output.push(line); previous = bullet;
    }
    const candidate = output.join(''), count = t => Math.ceil([...t].reduce((sum,c)=>sum+(c.codePointAt(0)<128?1:4),0)/4);
    const before = count(text), after = count(candidate), saved = before-after;
    return {original:text,candidate,before:{count:before,method:'browser-heuristic',note:'瀏覽器示範僅粗估；桌面版使用內建 tokenizer。'},after:{count:after},saved_tokens:saved,saved_percent:before?Math.round(saved/before*10000)/100:0,changes,warnings:['這是瀏覽器粗估示範，並非模型 Token 帳單。','精簡候選需要人工檢查任務品質。'],diff:candidate===text?'無內容變更':`--- 原文\n${text}\n+++ 精簡候選\n${candidate}`,cost:request.input_price===null?null:{before:before*request.input_price*request.calls/1e6,after:after*request.input_price*request.calls/1e6,saved:saved*request.input_price*request.calls/1e6,calls:request.calls}};
  }
  async function analyze() {
    const request = {content:$('promptContent').value,encoding:'o200k_base',input_price:null,calls:1,remove_duplicates:$('promptDeduplicate').checked};
    if (!Number.isInteger(request.calls) || request.calls < 1 || request.calls > 10000000 || (request.input_price !== null && (!Number.isFinite(request.input_price) || request.input_price < 0))) throw Error('請檢查單價與呼叫次數。');
    const snapshot = JSON.stringify(request);
    const result = bridge.runtime === 'desktop' ? response(await bridge.call('analyze_prompt', request)) : mockAnalyze(request);
    if (snapshot !== JSON.stringify({content:$('promptContent').value,encoding:'o200k_base',input_price:null,calls:1,remove_duplicates:$('promptDeduplicate').checked})) return;
    analysis = result;
    $('promptMetrics').innerHTML = `<div><span>原文 Token</span><strong>${result.before.count}</strong></div><div><span>候選 Token</span><strong>${result.after.count}</strong></div><div><span>減少</span><strong>${result.saved_tokens} · ${result.saved_percent}%</strong></div><p>${esc(result.before.method)}：${esc(result.before.note)}</p><p>僅比較文字長度，不代表訂閱額度或完整任務費用。</p>`;
    $('promptWarnings').textContent = result.warnings.join(' '); $('promptCandidate').textContent = result.candidate || '（空白）'; $('promptDiff').textContent = result.diff || '無內容變更';
    $('promptChanges').innerHTML = result.changes.map(c=>`<li>第 ${c.line} 行：${esc(c.detail)}</li>`).join('');
    $('promptUseCandidate').disabled = result.candidate === result.original; $('promptReport').disabled = false;
  }
  function downloadReport() {
    if (!analysis) return;
    const blob = new Blob([JSON.stringify({schema_version:1,generated_at:new Date().toISOString(),...analysis},null,2)],{type:'application/json'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'prompt-analysis.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  }
  async function previewExport() {
    const request = {project_path:project(),relative_path:$('promptExportPath').value,content:$('promptContent').value};
    if (bridge.runtime !== 'desktop') { $('promptExportDiff').textContent = '瀏覽器示範不寫入本機資料夾；請在桌面 App 匯出，或複製內容。'; return; }
    const result = response(await bridge.call('preview_prompt_file',request));
    if (request.content !== $('promptContent').value || request.relative_path !== $('promptExportPath').value) return;
    exportPreview = {...request,base_hash:result.base_hash,expected_exists:result.exists};
    $('promptExportDiff').textContent = (result.exists ? '注意：將替換整份檔案，原檔會備份。\n' : '建立新的 Markdown 檔。\n') + (result.diff || '無內容變更');
    $('promptExportApply').disabled = result.compiled === result.original || !result.compiled.trim();
  }
  async function applyExport() {
    if (!exportPreview || exportPreview.content !== $('promptContent').value || exportPreview.relative_path !== $('promptExportPath').value) throw Error('請重新產生匯出預覽。');
    if (!window.confirm(`確認${exportPreview.expected_exists?'替換整份':'建立'} ${exportPreview.relative_path}？可從備份復原。`)) return;
    lastExport = response(await bridge.call('apply_prompt_file',{...exportPreview,confirm_replace:exportPreview.expected_exists}));
    exportPreview = null; $('promptExportApply').disabled = true; $('promptRestoreExport').disabled = false; toast('已匯出 Markdown。');
  }
  $('promptNew').addEventListener('click', run(async()=>{if(mayReplace()){await select(null);$('promptTitle').focus();toast('已建立空白草稿；儲存後才會加入清單。');}}));
  $('promptSave').addEventListener('click',run(()=>save()));
  $('promptArchive').addEventListener('click',run(async()=>{ if(!current) throw Error('請先儲存提示詞。'); await save(!current.archived); }));
  $('promptCopy').addEventListener('click',run(async()=>{ await navigator.clipboard.writeText($('promptContent').value); toast('已複製提示詞。'); }));
  $('promptSearch').addEventListener('input',renderLibrary);
  $('promptGroupAdd').addEventListener('click',run(async()=>{
    if(!state.project)throw Error('請先到「專案」選擇資料夾，再建立自己的群組。');
    const name=window.prompt('群組名稱（例如：畢業專題、客服、研究）');if(name===null)return;
    const value=name.trim();if(!value)throw Error('請填寫群組名稱。');
    if(bridge.runtime==='desktop')response(await bridge.call('create_prompt_group',project(),value));
    else {const all=mockGroups();if(all.includes(value))throw Error('已有相同名稱的群組。');all.push(value);localStorage.setItem(mockGroupsKey,JSON.stringify(all));}
    await reload();toast(`已建立「${value}」群組。`);
  }));
  for (const id of ['promptContent','promptDeduplicate','promptExportPath']) $(id).addEventListener('input',dirty);
  $('promptAnalyze').addEventListener('click',run(analyze));
  $('promptUseCandidate').addEventListener('click',()=>{ if(analysis && analysis.original===$('promptContent').value) { $('promptContent').value=analysis.candidate; dirty(); toast('候選已帶回草稿，請儲存新版本。'); } });
  $('promptReport').addEventListener('click',downloadReport);
  $('promptImport').addEventListener('click',run(async()=>{ const path=$('promptImportPath').value;if(!path)throw Error('請選擇 Markdown。'); const file=response(await bridge.call('read_memory_file',project(),path));await select(null);$('promptTitle').value=path.split('/').pop().replace(/\.md$/i,'');$('promptContent').value=file.content;dirty(); }));
  $('promptExportPreview').addEventListener('click',run(previewExport)); $('promptExportApply').addEventListener('click',run(applyExport));
  $('promptRestoreExport').addEventListener('click',run(async()=>{ if(lastExport){response(await bridge.call('restore_change',lastExport.change_id));lastExport=null;$('promptRestoreExport').disabled=true;toast('已復原匯出。');} }));
  const scenarios={general:['任務助理','請完成指定任務，列出待確認事項。','清楚的條列'],review:['程式審查者','檢查輸入程式，指出可重現的錯誤與修正建議。','問題、影響、位置、建議'],writing:['文字編輯','整理輸入文字，保留原始事實、數字與限制。','修訂後文字與變更摘要'],research:['研究助理','整理提供的資料，區分證據與推論。','研究問題、依據、限制、來源']};
  $('promptScenario').addEventListener('change',()=>{const v=scenarios[$('promptScenario').value];$('builderRole').value=v[0];$('builderTask').value=v[1];$('builderFormat').value=v[2];});
  $('promptBuild').addEventListener('click',run(async()=>{if(!$('builderTask').value.trim())throw Error('請填寫任務。');if($('promptContent').value.trim()&&!window.confirm('用模板取代目前未儲存的草稿？'))return;$('promptContent').value=[['角色','builderRole'],['任務','builderTask'],['背景與輸入','builderContext'],['限制','builderConstraints'],['輸出格式','builderFormat']].filter(([,id])=>$(id).value.trim()).map(([title,id])=>`## ${title}\n\n${$(id).value.trim()}`).join('\n\n')+'\n';dirty();}));
  reload().catch(error=>reportError(error.message));
  return {reload, async importDraft(draft){if(!mayReplace())return false;await select(null);for(const [key,id] of [['title','promptTitle'],['category','promptCategory'],['tags','promptTags'],['content','promptContent']])$(id).value=draft[key]||'';dirty();return true;}};
}
