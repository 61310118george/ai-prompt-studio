import { mountUsageGuide } from './usage-guide.js';
import { PROMPT_TEMPLATES } from './prompt-templates.js';
import { mountCloudAnalysis } from './cloud-analysis.js';
import { DEFAULT_PROMPT_TAG_TEMPLATES, buildPromptFromTags, loadPromptTemplateCatalog, mountMarkdownEditor, parseMarkdownSections, updateMarkdownSection } from './prompt-builder.js';
export function mountPromptWorkspace({ bridge, state, escapeHtml: esc, reportError, toast }) {
  const root = document.querySelector('#page-prompts');
  root.innerHTML = `
    <div class="page-intro"><div><h2>提示詞工作台</h2><p>套用範本或自行撰寫；儲存後會直接進入範本庫，可依群組拖曳整理。</p></div><span class="agent-chip">預設離線 · AI 分析需確認</span></div>
    <div class="prompt-layout">
      <section class="panel prompt-library"><div class="panel-heading library-panel-heading"><h3>提示詞範本庫</h3><button class="button secondary compact-button" id="promptGroupAdd">新增群組</button></div><div class="prompt-library-body template-library">
        <p class="library-help">按住卡片可跨群組或調整順序，拖移時會即時預覽位置。</p>
        <label class="template-search">搜尋範本<input id="promptSearch" type="search" placeholder="例如：客服、JSON、摘要"></label>
        <div id="templateGroups" class="template-groups"></div>
      </div>
      </section>
      <section class="panel"><div class="panel-heading prompt-editor-heading"><h3>提示詞編輯</h3><div class="prompt-file-actions"><button class="button secondary compact-button" id="promptNew" type="button" title="開始新的空白草稿">新增草稿</button><button class="button secondary compact-button" id="promptImportLocal" type="button">匯入本機提示詞</button><button class="button secondary compact-button" id="promptExportLocal" type="button">匯出本機提示詞</button></div></div>
        <div class="prompt-fields"><label>標題<input id="promptTitle" maxlength="20" placeholder="例如：產品需求審查"></label>
        <fieldset class="prompt-tag-field"><legend>標籤（非必填）</legend><p>可複選；建立提示詞時會套用對應模板。</p><div class="prompt-tag-options" id="promptTagOptions"></div></fieldset>
        <label>群組（若要加入提示詞範本庫請選擇）<select id="promptCategory"><option value="">（不選擇）</option></select></label>
        <div class="prompt-builder-action"><button class="button secondary" id="promptBuild" type="button" disabled>建立提示詞</button><span id="promptBuildHint">請先輸入標題，或匯入本機 Markdown。</span></div>
        <section class="prompt-structure-panel" id="promptStructurePanel" hidden aria-labelledby="promptStructureTitle"><div class="prompt-structure-heading"><strong id="promptStructureTitle">Markdown 項目</strong><span id="promptStructureCount"></span></div><div class="prompt-structure-grid"><label>選擇項目<select id="promptSectionSelect"></select></label><label>標題層級<select id="promptSectionLevel"><option value="1">H1</option><option value="2">H2</option><option value="3">H3</option><option value="4">H4</option><option value="5">H5</option><option value="6">H6</option></select></label><label class="wide">項目標題<input id="promptSectionTitle" maxlength="120"></label><label class="wide">項目內容<textarea id="promptSectionBody" rows="7"></textarea></label></div><button class="button secondary compact-button" id="promptSectionApply" type="button">套用此項目</button></section>
        <div class="prompt-content-heading"><label for="promptContent">預覽提示詞</label></div><pre id="promptContent" class="prompt-editor markdown-prompt-editor is-empty" contenteditable="plaintext-only" role="textbox" aria-multiline="true" aria-label="預覽提示詞" data-placeholder="可直接輸入 Markdown，或先建立／匯入提示詞。" spellcheck="false"></pre>
        <div class="inline-actions prompt-actions"><button class="button primary" id="promptSave">儲存版本</button><button class="button secondary" id="promptCopy">複製</button><button class="button secondary" id="promptArchive">封存</button></div>
      </div></section>
  </div>`;
  const $ = (id) => root.querySelector(`#${id}`);
  const markdownEditor = mountMarkdownEditor($('promptContent'), () => dirty());
  const usage = document.createElement('div'); usage.className = 'usage-guide';
  root.querySelector('.prompt-actions').after(usage);
  const updateUsage = mountUsageGuide(usage, state, () => root.querySelector('#promptContent').value);
  const updateCloud = mountCloudAnalysis({
    root:usage,
    bridge,
    content:()=>root.querySelector('#promptContent').value,
    onApply:value=>{root.querySelector('#promptContent').value=value;dirty();root.querySelector('#promptContent').focus();toast('AI 優化結果已帶回草稿，請儲存新版本。');},
  });
  let current = null, entries = [], groups = [], templatePreferences = [], cardOrder = [], loadEpoch = 0, draftTags = '', importedPrompt = false, tagCatalog = DEFAULT_PROMPT_TAG_TEMPLATES;
  const response = (r) => { if (!r?.ok) throw Error(r?.error || '本機操作失敗'); return r.data; };
  const personalLibraryScope = '__local_prompt_library__';
  const libraryProject = () => state.project?.path || personalLibraryScope;
  const run = (fn) => async () => { reportError(''); try { await fn(); } catch (error) { reportError(error.message); } };
  const dirty = () => {
    updateUsage();
    updateCloud();
  };
  const selectedTags = () => draftTags.split(/[,，]/).map(tag=>tag.trim()).filter(Boolean);
  const updateBuilderAction = () => {
    $('promptBuild').textContent=importedPrompt?'修正提示詞':'建立提示詞';
    $('promptBuild').disabled=!importedPrompt&&!$('promptTitle').value.trim();
    $('promptBuildHint').textContent=importedPrompt?'已匯入 Markdown；可辨識標題並逐項修正。':$('promptTitle').value.trim()?'可依所選標籤建立基本模板。':'請先輸入標題，或匯入本機 Markdown。';
  };
  const renderTagOptions = () => {
    const selected=selectedTags(),known=tagCatalog.map(item=>item.tag),tags=[...known,...selected.filter(tag=>!known.includes(tag))];
    $('promptTagOptions').innerHTML=tags.map(tag=>`<label class="prompt-tag-chip"><input type="checkbox" value="${esc(tag)}" ${selected.includes(tag)?'checked':''}><span>${esc(tag)}</span></label>`).join('');
    $('promptTagOptions').querySelectorAll('input').forEach(input=>input.addEventListener('change',()=>{draftTags=[...$('promptTagOptions').querySelectorAll('input:checked')].map(item=>item.value).join(',');dirty();}));
  };
  const closeStructureEditor = () => { $('promptStructurePanel').hidden=true; };
  const loadStructureSection = () => {
    const sections=parseMarkdownSections($('promptContent').value),section=sections[Number($('promptSectionSelect').value)||0];
    if(!section)return;
    $('promptSectionTitle').value=section.level?section.title:'';
    $('promptSectionTitle').disabled=section.level===0;
    $('promptSectionLevel').value=String(section.level||1);
    $('promptSectionLevel').disabled=section.level===0;
    $('promptSectionBody').value=section.body;
  };
  const openStructureEditor = () => {
    const sections=parseMarkdownSections($('promptContent').value);
    $('promptSectionSelect').innerHTML=sections.map((section,index)=>`<option value="${index}">${section.level?`${'　'.repeat(Math.max(0,section.level-1))}H${section.level} `:''}${esc(section.title)}</option>`).join('');
    $('promptStructureCount').textContent=`${sections.length} 個項目`;
    $('promptStructurePanel').hidden=false;
    loadStructureSection();
    return sections.length;
  };
  const values = () => ({ title: $('promptTitle').value, category: $('promptCategory').value, tags: draftTags, content: $('promptContent').value });
  const mayReplace = () => !Object.entries(values()).some(([key,value])=>value !== (current?.[key] || '')) || window.confirm('目前有尚未儲存的草稿，確定換成另一份？');
  const resolvedTemplates = () => PROMPT_TEMPLATES.map((item,index)=>{
    const preference=templatePreferences.find(entry=>entry.template_key===item.id);
    return {item,index,category:preference?.category||item.category,hidden:Boolean(preference?.hidden)};
  });
  const defaultGroups = () => [...new Set(resolvedTemplates().filter(item=>!item.hidden).map(item=>item.category).concat(['一般']))];
  const applyTemplate = async (index) => {
    if(!mayReplace())return;
    const template=PROMPT_TEMPLATES[Number(index)]; await select(null);
    for(const [key,id] of [['title','promptTitle'],['category','promptCategory'],['content','promptContent']])$(id).value=template[key];
    draftTags=template.tags||'';
    renderTagOptions();updateBuilderAction();dirty();$('promptContent').focus();toast('範本已帶入草稿，可直接修改標題；儲存後會加入範本庫。');
  };
  async function select(item) {
    current = item;
    for (const [key, id] of [['title','promptTitle'],['content','promptContent'],['category','promptCategory']]) $(id).value = item?.[key] || '';
    draftTags=item?.tags||'';
    importedPrompt=false;closeStructureEditor();renderTagOptions();updateBuilderAction();
    $('promptArchive').textContent = item?.archived ? '取消封存' : '封存';
    dirty();
  }
  function renderLibrary() {
    const query = $('promptSearch').value.trim().toLocaleLowerCase();
    const visible = entries.filter(item => !query || [item.title,item.content,item.category,item.tags].join(' ').toLocaleLowerCase().includes(query));
    const names = [...new Set(defaultGroups().concat(groups.map(group=>group.name), visible.map(item=>item.category)).filter(Boolean))];
    const selectedCategory=$('promptCategory').value;
    $('promptCategory').innerHTML = `<option value="">（不選擇）</option>${names.map(name=>`<option value="${esc(name)}">${esc(name)}</option>`).join('')}`;
    $('promptCategory').value=names.includes(selectedCategory)?selectedCategory:'';
    const matchesTemplate = template => !query || [template.title,template.category,template.tags,template.content].join(' ').toLocaleLowerCase().includes(query);
    const templates = resolvedTemplates();
    $('templateGroups').innerHTML = names.map(name => {
      const builtins = templates.filter(({item,category,hidden})=>!hidden&&category===name&&matchesTemplate(item));
      const saved = visible.filter(item=>(item.category||'一般')===name);
      const totalCards = templates.filter(item=>!item.hidden&&item.category===name).length + entries.filter(item=>(item.category||'一般')===name).length;
      const positions = new Map(cardOrder.filter(item=>item.group_name===name).map(item=>[item.card_key,item.sort_order]));
      const cardItems = [
        ...builtins.map(({item,index})=>({key:`template:${item.id}`,markup:`<article class="template-card-frame builtin-template-frame" data-template-card="${esc(item.id)}" data-card-key="template:${esc(item.id)}" data-drag-kind="template" data-drag-id="${esc(item.id)}" data-drag-title="${esc(item.title)}"><span class="template-drag-grip" aria-hidden="true">⋮⋮</span><button class="template-card builtin-template" data-template="${index}" title="開啟範本；按住卡片可拖曳"><span class="template-card-title">${esc(item.title)}</span></button><button class="template-delete" type="button" data-delete-template="${esc(item.id)}" aria-label="刪除 ${esc(item.title)}">刪除</button></article>`})),
        ...saved.map(item=>({key:`prompt:${item.id}`,markup:`<article class="template-card-frame" data-prompt-card="${item.id}" data-card-key="prompt:${item.id}" data-drag-kind="prompt" data-drag-id="${item.id}" data-drag-title="${esc(item.title)}"><span class="template-drag-grip" aria-hidden="true">⋮⋮</span><button class="template-card saved-template" data-prompt-id="${item.id}" title="開啟範本；按住卡片可拖曳"><span class="template-card-title">${esc(item.title)}</span></button><button class="template-delete" type="button" data-delete-prompt="${item.id}" aria-label="刪除 ${esc(item.title)}">刪除</button></article>`})),
      ];
      cardItems.sort((a,b)=>{
        const aPosition=positions.get(a.key),bPosition=positions.get(b.key);
        if(aPosition!==undefined&&bPosition!==undefined)return aPosition-bPosition;
        if(aPosition!==undefined)return -1;if(bPosition!==undefined)return 1;return 0;
      });
      const cards = cardItems.map(item=>item.markup).join('') || '<p class="empty-state group-empty">把已儲存的範本拖到這裡。</p>';
      const deleteButton = name === '一般' ? '' : `<button class="template-group-delete" type="button" data-delete-group="${esc(name)}" title="刪除群組" aria-label="刪除 ${esc(name)} 群組">×</button>`;
      return `<section class="template-group" data-group-name="${esc(name)}"><header><div class="template-group-title"><strong>${esc(name)}</strong><span class="template-group-count" aria-label="${totalCards} 個範本">${totalCards}</span></div>${deleteButton}</header><div class="template-group-items">${cards}</div></section>`;
    }).join('') || '<p class="empty-state">尚無範本。建立草稿並儲存後會出現在這裡。</p>';
    $('templateGroups').querySelectorAll('[data-template]').forEach(button=>button.addEventListener('click',event=>{
      if(button.closest('[data-drag-kind]')?.dataset.dragSuppress==='true'){event.preventDefault();return;}
      run(()=>applyTemplate(button.dataset.template))();
    }));
    $('templateGroups').querySelectorAll('[data-prompt-id]').forEach(button=>{
      button.addEventListener('click',event=>{
        if(button.closest('[data-drag-kind]')?.dataset.dragSuppress==='true'){event.preventDefault();return;}
        run(()=>select(entries.find(item=>String(item.id)===button.dataset.promptId)))();
      });
    });
    $('templateGroups').querySelectorAll('[data-delete-group]').forEach(button=>button.addEventListener('click',run(()=>deleteGroup(button.dataset.deleteGroup))));
    $('templateGroups').querySelectorAll('[data-delete-prompt]').forEach(button=>button.addEventListener('click',run(()=>deletePrompt(button.dataset.deletePrompt))));
    $('templateGroups').querySelectorAll('[data-delete-template]').forEach(button=>button.addEventListener('click',run(()=>deleteBuiltinTemplate(button.dataset.deleteTemplate))));
    $('templateGroups').querySelectorAll('[data-drag-kind]').forEach(installCardDrag);
  }
  function installCardDrag(card) {
    card.addEventListener('pointerdown',event=>{
      if(event.button!==0||event.target.closest('[data-delete-prompt],[data-delete-template]'))return;
      event.preventDefault();document.getSelection()?.removeAllRanges();
      const pointerId=event.pointerId,startX=event.clientX,startY=event.clientY;
      const sourceGroup=card.closest('[data-group-name]')?.dataset.groupName||'';
      const sourceOrder=[...card.closest('.template-group-items')?.querySelectorAll('[data-card-key]')||[]].map(item=>item.dataset.cardKey);
      let dragging=false,ghost=null,placeholder=null,targetGroup=null,offsetX=0,offsetY=0;
      const clearTargets=()=>root.querySelectorAll('.template-group.drag-over').forEach(group=>group.classList.remove('drag-over'));
      const cleanup=()=>{
        window.removeEventListener('pointermove',move,true);window.removeEventListener('pointerup',finish,true);window.removeEventListener('pointercancel',cancel,true);
        clearTargets();ghost?.remove();placeholder?.remove();card.classList.remove('drag-source');card.setAttribute('aria-grabbed','false');document.body.classList.remove('template-drag-active');
      };
      const begin=()=>{
        dragging=true;document.getSelection()?.removeAllRanges();const rect=card.getBoundingClientRect();offsetX=startX-rect.left;offsetY=startY-rect.top;
        placeholder=document.createElement('div');placeholder.className='template-card-placeholder';placeholder.style.height=`${rect.height}px`;placeholder.setAttribute('aria-hidden','true');card.before(placeholder);
        ghost=card.cloneNode(true);ghost.classList.add('template-drag-ghost');ghost.removeAttribute('data-prompt-card');ghost.removeAttribute('data-template-card');ghost.querySelectorAll('button').forEach(button=>button.tabIndex=-1);
        ghost.style.width=`${rect.width}px`;document.body.append(ghost);card.classList.add('drag-source');card.setAttribute('aria-grabbed','true');document.body.classList.add('template-drag-active');
      };
      const position=(x,y)=>{if(ghost)ghost.style.transform=`translate3d(${x-offsetX}px,${y-offsetY}px,0) rotate(1.2deg)`;};
      const move=moveEvent=>{
        if(moveEvent.pointerId!==pointerId)return;
        if(!dragging&&Math.hypot(moveEvent.clientX-startX,moveEvent.clientY-startY)<7)return;
        if(!dragging)begin();moveEvent.preventDefault();document.getSelection()?.removeAllRanges();position(moveEvent.clientX,moveEvent.clientY);clearTargets();
        const placeholderRect=placeholder.getBoundingClientRect();
        const overPlaceholder=moveEvent.clientX>=placeholderRect.left&&moveEvent.clientX<=placeholderRect.right&&moveEvent.clientY>=placeholderRect.top&&moveEvent.clientY<=placeholderRect.bottom;
        const element=document.elementFromPoint(moveEvent.clientX,moveEvent.clientY),hovered=element?.closest('[data-card-key]')||null;
        targetGroup=(overPlaceholder?placeholder.closest('[data-group-name]'):(hovered?.closest('[data-group-name]')||element?.closest('[data-group-name]')))||null;
        targetGroup?.classList.add('drag-over');
        if(targetGroup&&!overPlaceholder){
          const items=targetGroup.querySelector('.template-group-items');
          if(hovered&&hovered!==card){
            const rect=hovered.getBoundingClientRect(),after=moveEvent.clientY>rect.top+rect.height/2,reference=after?hovered.nextSibling:hovered;
            if(reference!==placeholder)items.insertBefore(placeholder,reference);
          }else if(!hovered&&placeholder.parentElement!==items){items.append(placeholder);}
          else if(!hovered&&element?.closest('.template-group-items')===items){items.append(placeholder);}
        }
        if(moveEvent.clientY<90)window.scrollBy(0,-12);else if(moveEvent.clientY>window.innerHeight-70)window.scrollBy(0,12);
      };
      const finish=upEvent=>{
        if(upEvent.pointerId!==pointerId)return;
        const destination=targetGroup?.dataset.groupName||'';
        const orderedKeys=targetGroup?[...targetGroup.querySelector('.template-group-items').children].filter(item=>item!==card).map(item=>item===placeholder?card.dataset.cardKey:item.dataset.cardKey).filter(Boolean):[];
        const changed=Boolean(dragging&&destination&&(destination!==sourceGroup||orderedKeys.join('|')!==sourceOrder.join('|')));
        if(dragging){card.dataset.dragSuppress='true';setTimeout(()=>{if(card.isConnected)delete card.dataset.dragSuppress;},80);}
        if(changed&&placeholder?.isConnected){placeholder.replaceWith(card);placeholder=null;}
        cleanup();
        if(changed)run(()=>moveDraggedCard(card.dataset.cardKey,destination,orderedKeys))();
      };
      const cancel=cancelEvent=>{if(cancelEvent.pointerId===pointerId)cleanup();};
      window.addEventListener('pointermove',move,true);window.addEventListener('pointerup',finish,true);window.addEventListener('pointercancel',cancel,true);
    });
  }
  async function moveDraggedCard(cardKey,name,orderedKeys) {
    document.body.classList.add('template-order-saving');
    try {
      response(await bridge.call('place_prompt_card',libraryProject(),cardKey,name,orderedKeys));
      const [kind,id]=cardKey.split(':');
      if(kind==='prompt'&&String(current?.id)===id){$('promptCategory').value=name;current={...current,category:name};}
      toast(`已更新「${name}」群組的卡片順序。`);await reload();
    } finally {
      document.body.classList.remove('template-order-saving');
    }
  }
  async function deleteBuiltinTemplate(key) {
    const template=PROMPT_TEMPLATES.find(item=>item.id===key);if(!template)throw Error('找不到要刪除的內建範本。');
    if(!window.confirm(`從目前範本庫刪除「${template.title}」？`))return;
    const preference=templatePreferences.find(item=>item.template_key===key);
    response(await bridge.call('set_prompt_template_preference',libraryProject(),key,preference?.category||template.category,true));
    await playDeleteAnimation('template',key);await reload();toast(`已刪除「${template.title}」。`);
  }
  function playDeleteAnimation(type,id) {
    const attribute=type==='template'?'templateCard':'promptCard';
    const card=[...$('templateGroups').querySelectorAll(type==='template'?'[data-template-card]':'[data-prompt-card]')].find(item=>String(item.dataset[attribute])===String(id));
    if(!card)return Promise.resolve();
    card.classList.add('is-deleting');card.setAttribute('aria-busy','true');
    return new Promise(resolve=>{let settled=false;const finish=()=>{if(settled)return;settled=true;resolve();};card.addEventListener('animationend',finish,{once:true});setTimeout(finish,520);});
  }
  async function deleteGroup(name) {
    const affected=entries.filter(item=>item.category===name).length;
    const builtinKeys=resolvedTemplates().filter(item=>item.category===name&&!item.hidden).map(item=>item.item.id);
    const totalAffected=affected+builtinKeys.length;
    if(!window.confirm(`刪除「${name}」群組？${totalAffected?`\n\n其中 ${totalAffected} 個範本會移回「一般」，不會被刪除。`:''}`))return;
    response(await bridge.call('delete_prompt_group',libraryProject(),name,builtinKeys));
    if(current?.category===name){current={...current,category:'一般'};$('promptCategory').value='一般';}
    await reload();toast(`已刪除「${name}」群組${totalAffected?`，${totalAffected} 個範本已移回「一般」`:''}。`);
  }
  async function deletePrompt(id) {
    const item=entries.find(entry=>String(entry.id)===String(id));if(!item)throw Error('找不到要刪除的範本。');
    if(!window.confirm(`刪除「${item.title}」？\n\n這會同時刪除該範本的版本紀錄，無法復原。`))return;
    response(await bridge.call('delete_prompt',libraryProject(),item.id));
    await playDeleteAnimation('prompt',item.id);
    if(String(current?.id)===String(item.id))await select(null);
    await reload();toast(`已刪除「${item.title}」。`);
  }
  async function reload(reset = false) {
    updateUsage();
    const epoch = ++loadEpoch;
    if (reset) await select(null);
    const query = '', category = '', archived = false;
    const result = response(await bridge.call('list_prompts', libraryProject(), query, category, archived));
    if (epoch !== loadEpoch) return;
    entries = result;
    groups = response(await bridge.call('list_prompt_groups', libraryProject()));
    if (epoch !== loadEpoch) return;
    templatePreferences = response(await bridge.call('list_prompt_template_preferences', libraryProject()));
    if (epoch !== loadEpoch) return;
    cardOrder = response(await bridge.call('list_prompt_card_order', libraryProject()));
    if (epoch !== loadEpoch) return;
    renderLibrary();
  }
  async function save(archived = Boolean(current?.archived)) {
    const request = { ...values(), id: current?.id, version: current?.version, archived, project_path: libraryProject() };
    if (!request.title.trim() || !request.content.trim()) throw Error('請填寫標題與提示詞內容。');
    current = response(await bridge.call('save_prompt', request));
    $('promptArchive').textContent = current.archived ? '取消封存' : '封存';
    await reload(); toast('已儲存提示詞版本。');
  }
  $('promptNew').addEventListener('click', run(async()=>{if(mayReplace()){await select(null);$('promptTitle').focus();toast('已建立空白草稿；儲存後才會加入清單。');}}));
  $('promptSave').addEventListener('click',run(()=>save()));
  $('promptArchive').addEventListener('click',run(async()=>{ if(!current) throw Error('請先儲存提示詞。'); await save(!current.archived); }));
  $('promptCopy').addEventListener('click',run(async()=>{ await navigator.clipboard.writeText($('promptContent').value); toast('已複製提示詞。'); }));
  $('promptSearch').addEventListener('input',renderLibrary);
  $('promptGroupAdd').addEventListener('click',run(async()=>{
    const name=window.prompt('群組名稱（例如：畢業專題、客服、研究）');if(name===null)return;
    const value=name.trim();if(!value)throw Error('請填寫群組名稱。');
    response(await bridge.call('create_prompt_group',libraryProject(),value));
    await reload();toast(`已建立「${value}」群組。`);
  }));
  $('promptTitle').addEventListener('input',updateBuilderAction);
  $('promptSectionSelect').addEventListener('change',loadStructureSection);
  $('promptSectionApply').addEventListener('click',run(async()=>{
    $('promptContent').value=updateMarkdownSection($('promptContent').value,$('promptSectionSelect').value,{title:$('promptSectionTitle').value,level:$('promptSectionLevel').value,body:$('promptSectionBody').value});
    const selected=$('promptSectionSelect').value;openStructureEditor();$('promptSectionSelect').value=selected;loadStructureSection();dirty();toast('已更新預覽中的 Markdown 項目。');
  }));
  $('promptImportLocal').addEventListener('click',run(async()=>{
    if(!mayReplace())return;
    const file=response(await bridge.call('import_prompt_file'));if(!file)return;
    await select(null);$('promptTitle').value=String(file.name||'匯入提示詞').slice(0,20);$('promptContent').value=file.content;importedPrompt=true;updateBuilderAction();dirty();$('promptBuild').focus();toast(`已匯入 ${file.filename||file.name}；點擊「修正提示詞」可依 Markdown 項目編輯。`);
  }));
  $('promptExportLocal').addEventListener('click',run(async()=>{
    const content=$('promptContent').value;if(!content.trim())throw Error('提示詞內容為空白，無法匯出。');
    const file=response(await bridge.call('export_prompt_file',$('promptTitle').value||'my-prompt',content));if(!file)return;
    toast(`已匯出 ${file.filename}。`);
  }));
  $('promptBuild').addEventListener('click',run(async()=>{
    if(importedPrompt){const count=openStructureEditor();toast(`已辨識 ${count} 個 Markdown 項目，可從下拉選單逐項修正。`);return;}
    const title=$('promptTitle').value.trim();if(!title)throw Error('請先輸入標題。');
    if($('promptContent').value.trim()&&!window.confirm('用標籤模板取代目前的預覽提示詞？'))return;
    $('promptContent').value=buildPromptFromTags(title,selectedTags(),tagCatalog);const count=openStructureEditor();dirty();$('promptContent').focus();toast(`已建立基本提示詞與 ${count} 個 Markdown 項目。`);
  }));
  renderTagOptions();updateBuilderAction();
  loadPromptTemplateCatalog().then(catalog=>{tagCatalog=catalog;renderTagOptions();}).catch(()=>{});
  reload().catch(error=>reportError(error.message));
  return {reload, async importDraft(draft){if(!mayReplace())return false;await select(null);for(const [key,id] of [['title','promptTitle'],['category','promptCategory'],['content','promptContent']])$(id).value=draft[key]||'';draftTags=draft.tags||'';renderTagOptions();updateBuilderAction();dirty();return true;}};
}
