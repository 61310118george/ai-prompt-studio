export const GROUPS = {core:'核心記憶', prompts:'專案提示詞', outputs:'AI 輸出項目', skills:'專案技能'};
const OUTPUT_PATH = /(?:^|\/)(?:deliverables?|outputs?)(?:\/|$)|(?:企劃書|交付驗收|符合度|展示指南|第三方來源)/i;
export function fileGroup(file) { return file.group || (/((^|\/)skills\/|(^|\/)skill\.md$)/i.test(file.relative_path) ? 'skills' : file.recognized ? 'core' : OUTPUT_PATH.test(file.relative_path) ? 'outputs' : 'prompts'); }

// Section editing preserves frontmatter, code fences and all unselected text verbatim.
export function sectionsOf(text) {
  const lines = text.split(/(?<=\n)/); const result = []; let offset=0, fence=null, yaml=false;
  lines.forEach((line,index)=>{
    if(index===0 && line.trim()==='---') yaml=true;
    else if(yaml && line.trim()==='---') yaml=false;
    else if(!yaml) {
      const marker=line.match(/^ {0,3}(`{3,}|~{3,})/);
      if(marker) { if(!fence) fence=marker[1]; else if(marker[1][0]===fence[0] && marker[1].length>=fence.length) fence=null; }
      else if(!fence) { const heading=line.match(/^(#{1,6})[ \t]+(.+?)[\r\n]*$/); if(heading) result.push({title:heading[2],start:offset,body:offset+line.length,end:text.length}); }
    }
    offset+=line.length;
  });
  result.forEach((section,index)=>{section.end=result[index+1]?.start ?? text.length;});
  return result;
}
export function mountFileEditor({bridge, state, esc, toast, refreshed, toWorkbench}) {
  const dialog=document.createElement('dialog'); dialog.id='fileEditor'; dialog.className='file-editor';
  dialog.innerHTML=`<div class="editor-header"><div><h2 id="editorTitle">編輯文件</h2><p id="editorPath"></p></div><button class="button secondary" id="editorClose">關閉</button></div>
    <p class="source-note" id="editorHelp"></p><p id="editorError" class="global-message hidden" role="alert"></p>
    <div class="editor-grid"><section><h3>編輯內容</h3>
    <details id="quickEditor" open><summary>快速編輯章節</summary><label>選擇章節<select id="editorSection"></select></label><label>本章節內容<textarea id="editorSectionText"></textarea></label><button class="button secondary" id="editorSectionApply">更新章節草稿</button></details>
    <details id="newSectionEditor" open><summary>新增章節</summary><label>章節主題<input id="editorNewTitle" maxlength="120" placeholder="例如：測試與驗收規則"></label><label>章節內容<textarea id="editorNewContent" placeholder="填寫這個章節的內容"></textarea></label><button class="button secondary" id="editorInsert">加入章節草稿</button></details>
    <details id="editorAdvanced"><summary>進階：編輯 Markdown 全文</summary><label>Markdown 全文<textarea id="editorText" spellcheck="false"></textarea></label></details>
    <button class="button secondary" id="editorExtract">擷取專案重點到提示詞工作台</button><p class="field-help">摘錄核心文件與目前草稿的前段內容，保留來源。這是本機摘錄，不是 AI 摘要；到工作台確認後再存成範本。</p></section>
    <section><h3>修改後內容</h3><p class="field-help">右側即時顯示完整 Markdown 草稿。更新章節後會自動展開 Git 風格差異；綠色是新內容，紅色是原內容。</p><pre class="code-view" id="editorContentPreview"></pre><details id="editorDiffPanel"><summary>儲存前確認差異</summary><div class="diff-view" id="editorDiff" role="region" aria-label="文件差異"></div></details></section></div>
    <footer class="editor-footer"><span id="editorStatus" role="status">尚未修改</span><button class="button secondary" id="editorPreview">預覽變更</button><button class="button primary" id="editorSave" disabled>確認儲存</button></footer>`;
  dialog.setAttribute('aria-labelledby','editorTitle'); document.body.append(dialog);
  const $=id=>dialog.querySelector(`#${id}`); let file, path, project, preview, epoch=0, busy=false, opener;
  const response=r=>{if(!r?.ok)throw Error(r?.error||'檔案操作失敗');return r.data;};
  const error=message=>{$('editorError').textContent=message;$('editorError').classList.toggle('hidden',!message);};
  const diffMessage=message=>{$('editorDiff').innerHTML='';const row=document.createElement('div');row.className='diff-message';row.textContent=message;$('editorDiff').append(row);};
  function renderDiff(text){
    $('editorDiff').innerHTML='';if(!text?.trim())return diffMessage('沒有變更。');
    let oldLine=1,newLine=1;
    for(const line of text.split('\n')){
      const row=document.createElement('div');row.className='diff-row';
      const hunk=line.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      let oldNumber='',newNumber='',kind='context';
      if(hunk){oldLine=Number(hunk[1]);newLine=Number(hunk[2]);kind='hunk';}
      else if(line.startsWith('---')||line.startsWith('+++'))kind='meta';
      else if(line.startsWith('-')){oldNumber=oldLine++;kind='remove';}
      else if(line.startsWith('+')){newNumber=newLine++;kind='add';}
      else {oldNumber=oldLine++;newNumber=newLine++;}
      row.classList.add(`diff-${kind}`);
      for(const [className,value] of [['diff-old-number',oldNumber],['diff-new-number',newNumber],['diff-code',line]]){const span=document.createElement('span');span.className=className;span.textContent=String(value);row.append(span);}
      $('editorDiff').append(row);
    }
  }
  const invalidate=()=>{epoch++;preview=null;error('');$('editorContentPreview').textContent=$('editorText').value;$('editorSave').disabled=true;diffMessage('草稿已更新，請重新預覽。');$('editorStatus').textContent='尚未儲存';};
  function showSections(){const sections=sectionsOf($('editorText').value);$('editorSection').innerHTML='<option value="">選擇要修改的標題</option>'+sections.map((s,i)=>`<option value="${i}">${esc(s.title)}</option>`).join('');$('editorSectionText').value='';}
  async function task(fn){if(busy)return;busy=true;error('');const controls=[...dialog.querySelectorAll('textarea, input, select, #editorSectionApply, #editorInsert, #editorExtract')];controls.forEach(control=>control.disabled=true);try{await fn();}catch(e){error(e.message);}finally{busy=false;controls.forEach(control=>control.disabled=false);}}
  function close(){if(busy)return;if(file && ($('editorText').value!==file.content||pendingFields()) && !confirm('有尚未儲存的草稿，確定關閉？'))return;dialog.close();opener?.focus();}
  $('editorClose').onclick=close;dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
  $('editorText').addEventListener('input',()=>{invalidate();showSections();});
  $('editorSection').onchange=()=>{const s=sectionsOf($('editorText').value)[$('editorSection').value];$('editorSectionText').value=s ? $('editorText').value.slice(s.body,s.end) : '';};
  $('editorSectionApply').onclick=()=>task(async()=>{const text=$('editorText').value;const s=sectionsOf(text)[$('editorSection').value];if(!s)throw Error('請先選擇一個章節。');$('editorText').value=text.slice(0,s.body)+$('editorSectionText').value.replace(/\s*$/,'\n\n')+text.slice(s.end);invalidate();showSections();await previewDraft();});
  $('editorInsert').onclick=()=>{const title=$('editorNewTitle').value.trim().replace(/^#+\s*/,''),content=$('editorNewContent').value.trim();if(!title||!content)return error('請填寫章節主題與章節內容。'); if(sectionsOf($('editorText').value).some(s=>s.title.replace(/\s+#+$/,'').trim()===title)) return error('這個章節已存在，請從章節選單編輯。');$('editorText').value=$('editorText').value.replace(/\s*$/,'')+`\n\n## ${title}\n\n${content}\n`;$('editorNewTitle').value='';$('editorNewContent').value='';invalidate();showSections();};
  $('editorExtract').onclick=()=>task(async()=>{
    if(pendingFields())throw Error('請先更新章節草稿或加入新章節，再擷取重點。');
    const candidates=(state.scan?.files||[]).filter(f=>fileGroup(f)==='core'&&f.relative_path!==path);
    const selected=[path,...candidates.slice(0,7).map(f=>f.relative_path)];let total=0;
    const blocks=[];
    for(const source of selected){
      const text=source===path?$('editorText').value:response(await bridge.call('read_memory_file',project,source)).content;
      const excerpt=text.trim().slice(0,Math.min(1800,12000-total));if(!excerpt)continue;total+=excerpt.length;
      blocks.push(`## 來源：${source}${source===path?'（目前編輯草稿）':''}\n\n${excerpt}${text.trim().length>excerpt.length?'\n\n[此文件僅摘錄前段，請回原檔補查]':''}`);
    }
    const draft={title:`${state.project.name}｜專案重點範本`,category:'專案背景',tags:'專案重點,本機摘錄',content:`# 專案重點（待人工確認）\n\n以下是最多 8 份文件的原文前段摘錄，不是語意摘要。未寫回原檔；請保留必要條件、刪除敏感資訊後再儲存為範本。\n${candidates.length>7?'\n[核心文件超過上限，部分未納入]\n':''}\n${blocks.join('\n\n')}\n\n## 本次任務\n\n[填寫要完成的工作與輸出格式]\n`};
    if(await toWorkbench(draft)){dialog.close();toast('已帶入工作台草稿，確認後按「儲存版本」保存範本。');}
  });
  function pendingFields(){const s=sectionsOf($('editorText').value)[$('editorSection').value];return Boolean($('editorNewTitle').value.trim()||$('editorNewContent').value.trim()||(s&&$('editorSectionText').value!==$('editorText').value.slice(s.body,s.end)));}
  async function previewDraft(){
    if(pendingFields())throw Error('還有未加入的編輯內容，請先按「更新章節草稿」或「加入章節草稿」。');
    const generation=epoch, content=$('editorText').value;
    const result=response(await bridge.call('preview_prompt_file',{project_path:project,relative_path:path,content}));
    if(generation!==epoch)return;
    if(result.base_hash!==file.hash)throw Error('檔案已被其他程式修改。請保留草稿，關閉後重新開啟檔案再合併。');
    preview={project_path:project,relative_path:path,content,base_hash:result.base_hash,expected_exists:result.exists,confirm_replace:true};
    renderDiff(result.diff);$('editorDiffPanel').open=true;$('editorSave').disabled=content===file.content||!content.trim();$('editorStatus').textContent='已預覽，尚未寫入';
  }
  $('editorPreview').onclick=()=>task(previewDraft);
  $('editorSave').onclick=()=>task(async()=>{
    if(!preview||pendingFields()||preview.content!==$('editorText').value)throw Error('請先更新草稿並重新預覽。');
    const request=preview; $('editorSave').disabled=true;
    response(await bridge.call('apply_prompt_file',request));
    file=response(await bridge.call('read_memory_file',project,path));preview=null;
    $('editorStatus').textContent='已儲存並建立備份';toast('文件已儲存，原版已備份。');await refreshed(path);
  });
  return {async open(relativePath){
    if(dialog.open)return; project=state.project?.path;if(!project)throw Error('請先選擇專案。');
    const loaded=response(await bridge.call('read_memory_file',project,relativePath));
    path=relativePath;file=loaded;preview=null;epoch++;opener=document.activeElement;
    const group=fileGroup(state.scan.files.find(f=>f.relative_path===path)||{relative_path:path});
    const help={core:'核心記憶：集中編輯協作規則、限制與驗收標準。既有標題與手寫內容會保留。',prompts:'專案提示詞：以章節整理任務、背景與輸出格式。一般文件不一定由 Agent 自動載入。',skills:'專案技能：整理觸發情境、操作步驟與驗證。YAML 中的 name／description 可在全文編輯，快速章節編輯不會改動它。',outputs:'AI 輸出項目：整理企劃書、驗收或展示等交付內容。編輯前請確認內容仍符合實際成果。'};
    $('editorTitle').textContent=`編輯${GROUPS[group]}`;$('editorPath').textContent=path;$('editorHelp').textContent=help[group];
    $('editorText').value=file.content;$('editorContentPreview').textContent=file.content;$('editorNewTitle').value='';$('editorNewContent').value='';$('editorAdvanced').open=false;$('editorDiffPanel').open=false;
    diffMessage('尚未產生預覽。');$('editorSave').disabled=true;$('editorStatus').textContent='尚未修改';error('');showSections();dialog.showModal();$('editorSection').focus();
  }};
}
