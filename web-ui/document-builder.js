import { DOCUMENT_TYPES, fieldsFor, profileNote, profileKey, TOPICS, topicContext, compileDocument } from './document-catalog.js';
import { mountDocumentAi } from './document-ai.js';

export function mountDocumentBuilder({root, bridge, esc, getTitle, getContent, setContent, onTags, onChange}) {
  const host=root.querySelector('#documentBuilder');
  host.innerHTML=`<fieldset class="document-type-tabs" aria-label="文件類型">${Object.entries(DOCUMENT_TYPES).map(([key,label])=>`<label><input type="radio" name="documentType" value="${key}" id="documentType-${key}"><span>${label}</span></label>`).join('')}</fieldset>
    <p id="documentPurpose" class="document-purpose" hidden></p>
    <div id="documentFormArea" hidden><fieldset class="prompt-tag-field"><legend>標籤（各選一項，非必填）</legend><div id="documentTopics" class="prompt-tag-options"></div><div id="promptTagOptions" class="prompt-tag-options document-subtopics"></div></fieldset>
    <button type="button" class="button secondary document-write-button" id="documentAiWrite" disabled>AI 輔助撰寫</button><p id="documentAiMessage" role="status"></p>
    <nav id="documentSteps" class="document-steps" aria-label="專案文件進度" hidden></nav>
    <div id="documentFields" class="document-fields"></div>
    <div id="documentStepActions" class="inline-actions" hidden><button type="button" class="button secondary" id="documentPrevious">上一步</button><button type="button" class="button primary" id="documentNext">完成並繼續</button></div>
    </div>`;
  const $=id=>host.querySelector(`#${id}`), stages=['core','memory','skill'];
  $('documentAiWrite').before(root.querySelector('#promptTitleField'));
  $('documentFormArea').prepend(root.querySelector('#promptCategory').closest('label'));
  const empty=()=>({schemaVersion:2,mode:'',active:'core',major:'',minors:[],documents:{},topicDrafts:{},skillName:'project-workflow'});
  let data=empty(), revision=0, catalog=[], aiBusy=false;
  const active=()=>data.mode==='project'?data.active:data.mode;
  const doc=()=>data.documents[active()]||(data.documents[active()]={fields:{},content:''});
  const stash=()=>{if(active())doc().content=getContent();};
  const signature=()=>JSON.stringify([getTitle(),doc().fields,tags(),active()==='skill'?data.skillName:'']);
  const assertSynced=(key)=>{
    const item=data.documents[key];
    if(item&&Object.values(item.fields).some(value=>value.trim())&&item.builtFields!==JSON.stringify([getTitle(),item.fields,tags(),key==='skill'?data.skillName:'']))
      throw Error(`「${DOCUMENT_TYPES[key]}」表單已變更，請先按「建立提示詞」更新預覽，再輸出。`);
  };
  const tags=()=>data.major?[data.major,...data.minors.map(minor=>`${data.major}/${minor}`)].join(','):'';
  const gate=()=>{
    const hasTitle=Boolean(getTitle().trim());
    host.querySelectorAll('[name="documentType"]').forEach(input=>{input.checked=input.value===data.mode;});
    $('documentFormArea').hidden=!data.mode;
    $('documentPurpose').hidden=!data.mode;
    $('documentPurpose').textContent=profileNote(data.mode);
    $('documentFields').hidden=!hasTitle;
    $('documentSteps').hidden=!hasTitle||data.mode!=='project';
    $('documentStepActions').hidden=!hasTitle||data.mode!=='project';
    root.querySelector('#documentEditor').hidden=!hasTitle||!data.mode;
    $('documentAiWrite').disabled=aiBusy||!hasTitle||!data.mode;
    host.querySelectorAll('[data-field-ai]').forEach(button=>{button.disabled=aiBusy||!doc().fields[button.dataset.fieldAi]?.trim();});
  };
  const notify=()=>{revision++;gate();onChange();};
  const renderTags=()=>{
    $('documentTopics').innerHTML=Object.keys(TOPICS).map(name=>`<label class="prompt-tag-chip"><input type="radio" name="documentTopic" value="${esc(name)}"><span>${esc(name)}</span></label>`).join('');
    $('documentTopics').querySelectorAll('input').forEach(input=>{
      input.checked=data.major===input.value;
      input.onclick=()=>{if(data.major===input.value)return;switchTopic(input.value,[]);};
    });
    $('promptTagOptions').innerHTML=(TOPICS[data.major]||[]).map(name=>`<label class="prompt-tag-chip"><input type="radio" name="documentSubtopic" value="${esc(name)}"><span>${esc(name)}</span></label>`).join('');
    $('promptTagOptions').querySelectorAll('input').forEach(input=>{
      input.checked=data.minors.includes(input.value);
      input.onchange=()=>switchTopic(data.major,[input.value]);
    });
  };
  function switchTopic(major,minors){
    stash();data.topicDrafts ||= {};
    data.topicDrafts[profileKey(data.major,data.minors)]=structuredClone(data.documents);
    data.major=major;data.minors=minors;
    data.documents=structuredClone(data.topicDrafts[profileKey(major,minors)]||{});
    if(data.mode==='project')data.active='core';
    setContent(active()?doc().content:'');onTags(tags());renderTags();renderFields();renderSteps();notify();
  }
  const ai=mountDocumentAi({bridge,status:$('documentAiMessage'),busyChanged:value=>{aiBusy=value;gate();},
    snapshot:()=>({schema_version:2,major:data.major,minor:data.minors[0]||'',title:getTitle(),tags:tags(),document_type:active(),guidance:topicContext(data.major,data.minors),
      fields:structuredClone(active()?doc().fields:{}),source:getContent(),revision,mode:data.mode}),
    onApply:fields=>{Object.assign(doc().fields,fields);renderFields();notify();},
  });
  $('documentAiWrite').onclick=()=>ai.start('write');
  function renderFields(){
    if(!active()){$('documentFields').replaceChildren();return;}
    const fields=doc().fields;
    const schema=fieldsFor(active(),fields,data.major,data.minors);
    const groups=[...new Set(schema.map(field=>field.group))];
    $('documentFields').innerHTML=(active()==='skill'?'<label>技能識別名稱<input id="documentSkillName" maxlength="64" spellcheck="false"></label>':'')+
      groups.map(group=>`<section class="document-question-group"><h4>${esc(group)}</h4>${schema.filter(field=>field.group===group).map(field=>`<div class="document-field"><div class="section-ai-heading"><label for="documentField-${field.id}">${esc(field.label)}${field.required?'（必填）':''}</label><button type="button" class="button secondary compact-button document-revise-button" data-field-ai="${field.id}">AI 修正</button></div><p class="document-question" id="question-${field.id}">${esc(field.question)}</p><textarea id="documentField-${field.id}" data-document-field="${field.id}" rows="2" maxlength="${field.maxLength||20000}" aria-describedby="question-${field.id}" placeholder="請填寫你的實際需求；未確認可填待確認。"></textarea></div>`).join('')}</section>`).join('');
    $('documentFields').querySelectorAll('[data-document-field]').forEach(input=>{
      input.value=fields[input.dataset.documentField]||'';
      input.oninput=()=>{fields[input.dataset.documentField]=input.value;notify();};
    });
    $('documentFields').querySelectorAll('[data-field-ai]').forEach(button=>button.onclick=()=>ai.start('revise',button.dataset.fieldAi));
    if($('documentSkillName')){$('documentSkillName').value=data.skillName;$('documentSkillName').oninput=()=>{data.skillName=$('documentSkillName').value;notify();};}
  }
  function renderSteps(){
    const project=data.mode==='project';$('documentSteps').hidden=!project;$('documentStepActions').hidden=!project;
    $('documentSteps').innerHTML=project?stages.map((key,index)=>`<button type="button" class="document-step" data-stage="${key}" ${key===active()?'aria-current="step"':''}>${index+1}. ${DOCUMENT_TYPES[key]}${data.documents[key]?.content?.trim()?' ✓':''}</button>`).join(''):'';
    $('documentSteps').querySelectorAll('[data-stage]').forEach(button=>{
      const index=stages.indexOf(button.dataset.stage);
      button.disabled=stages.slice(0,index).some(key=>!data.documents[key]?.content?.trim());
      button.onclick=()=>switchStage(button.dataset.stage);
    });
    $('documentPrevious').disabled=active()==='core';
    $('documentNext').textContent=active()==='skill'?'完成技能文件':'完成並繼續';
  }
  function switchStage(next){stash();data.active=next;setContent(doc().content);renderFields();renderSteps();notify();}
  function build(){
    if(!data.mode||!getTitle().trim())throw Error('請填寫標題並選擇文件類型。');
    const next=compileDocument(active(),getTitle(),doc().fields,tags(),data.skillName);
    if(getContent().trim()&&getContent()!==next&&!window.confirm('用表單內容更新目前文件的 Markdown 預覽？其他文件不會變更。'))return false;
    // User-imported CSV templates are opt-in additions for the selected, qualified topic.
    const additions=catalog.filter(item=>data.minors.some(minor=>item.tag===`${data.major}/${minor}`));
    const extra=additions.map(item=>[item.role,item.task,item.requirements,item.output,item.acceptance].filter(Boolean).join('\n')).join('\n\n');
    setContent(next+(extra?`\n## 自訂模板補充\n\n${extra}\n`:''));stash();doc().builtFields=signature();renderSteps();notify();return true;
  }
  host.querySelectorAll('[name="documentType"]').forEach(input=>input.onchange=()=>{
    stash();data.mode=input.value;if(data.mode==='project')data.active='core';
    setContent(doc().content);renderFields();renderSteps();gate();notify();
  });
  $('documentPrevious').onclick=()=>switchStage(stages[Math.max(0,stages.indexOf(active())-1)]);
  $('documentNext').onclick=()=>{
    try{
      $('documentBuilderError').textContent='';
      const changed=Object.values(doc().fields).some(value=>value.trim())&&doc().builtFields!==signature();
      if((!getContent().trim()||changed)&&!build())return;
      stash();
      if(active()==='skill'){renderSteps();notify();return;}
      switchStage(stages[stages.indexOf(active())+1]);
    }catch(error){root.querySelector('#documentBuilderError').textContent=error.message;}
  };
  const error=document.createElement('p');error.id='documentBuilderError';error.setAttribute('role','alert');host.append(error);
  renderTags();gate();
  return {
    build, gate, tags, active, assertSynced:()=>assertSynced(active()), isProject:()=>data.mode==='project', ready:()=>Boolean(data.mode&&getTitle().trim()),
    setCatalog:items=>{catalog=items;},
    snapshot:()=>{stash();return structuredClone(data);},
    restore:(value,legacy=false)=>{
      if(typeof value==='string'){try{value=JSON.parse(value);}catch{value=null;}}
      data=value?.mode?structuredClone(value):empty();
      data.documents ||= {};data.topicDrafts ||= {};data.schemaVersion=2;
      if(!value?.mode&&legacy){data.mode='memory';data.documents.memory={fields:{},content:getContent()};}
      if(!DOCUMENT_TYPES[data.mode])data.mode='';
      if(!stages.includes(data.active))data.active='core';
      if(!TOPICS[data.major])data.major='';
      const previousTags=[data.major,...(data.minors||[]).map(minor=>`${data.major}/${minor}`)].filter(Boolean).join(',');
      data.minors=(data.minors||[]).filter(minor=>TOPICS[data.major]?.includes(minor)).slice(0,1);
      if(previousTags!==tags()||value?.schemaVersion!==2)Object.values(data.documents).forEach(item=>{delete item.builtFields;});
      onTags(tags());
      data.skillName ||= 'project-workflow';
      revision++;renderTags();renderFields();renderSteps();gate();
    },
    documents:()=>{stash();stages.forEach(assertSynced);return Object.fromEntries(stages.map(key=>[key,data.documents[key]?.content||'']));},
  };
}
