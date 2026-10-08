import { GROUPS, fileGroup } from './file-editor.js';
export function mockHealth(files, contents) {
  const issues=[], repeated=new Map(), identical=new Map();
  const add=(f,line,level,code,title)=>issues.push({path:f.relative_path,line,end_line:line,level,code,title,detail:'規則命中不代表一定有害，請確認此處是否為範例或必要內容。',group:fileGroup(f),modified_at:f.modified_at});
  const patterns=[[/password\s*[:=]\s*\S+|密碼\s*[:：=]\s*\S+|\bsk-[\w-]{20,}|\bgh[pousr]_[\w]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY/i,'error','possible_secret','疑似敏感資訊'],[/ignore\s+(?:all\s+)?previous\s+instructions|忽略.{0,8}(?:之前|所有|系統).{0,5}(?:指令|規則)|(?:reveal|show).{0,30}system prompt|(?:繞過|停用).{0,8}(?:安全|限制)|curl .+\|\s*(?:bash|sh)|[\u200b-\u200d\u202a-\u202e]/i,'warning','prompt_injection','疑似攻擊指令'],[/^\s*(TODO|TBD|待補|待填)\s*[:：]?\s*$/i,'info','placeholder','未完成的內容']];
  files.forEach(f=>{const content=contents[f.relative_path]||'';
    if(!content.trim())add(f,null,'info','empty_file','空白文件');
    else {const list=identical.get(content)||[];list.push(f);identical.set(content,list);}
    content.split('\n').forEach((line,i)=>{patterns.forEach(([regex,level,code,title])=>{if(regex.test(line))add(f,i+1,level,code,title);});const normalized=line.replace(/^\s*[-*+]\s*/,'').trim().toLowerCase();if(normalized.length>=12&&!normalized.startsWith('#')){const list=repeated.get(normalized)||[];list.push([f,i+1]);repeated.set(normalized,list);}});
  });
  repeated.forEach(list=>{if(list.length>1)list.forEach(([f,line])=>add(f,line,'info','duplicate_rule','重複段落／規則'));});
  identical.forEach(list=>{if(list.length>1)list.forEach(f=>add(f,null,'info','duplicate_file','內容完全相同的文件'));});
  return {issues,files:files.map(f=>({...f,issues:issues.filter(i=>i.path===f.relative_path)})).filter(f=>f.issues.length),summary:{errors:issues.filter(i=>i.level==='error').length,warnings:issues.filter(i=>i.level==='warning').length,info:issues.filter(i=>i.level==='info').length,scanned_files:files.length},scan_warnings:[],scope_note:'瀏覽器示範：檢查示範 Markdown。桌面版使用完整本機規則；可能誤報或漏報。'};
}
export function renderHealthPanel({result,bridge,project,esc,openEditor}) {
  const list=document.querySelector('#healthFiles'), preview=document.querySelector('#healthPreview');
  const stats=[result.summary.errors,result.summary.warnings,result.summary.info,result.summary.scanned_files];
  document.querySelectorAll('#healthStats strong').forEach((n,i)=>n.textContent=stats[i]??0);
  document.querySelector('#healthScope').textContent=[result.scope_note,...(result.scan_warnings||[])].join(' ');
  list.replaceChildren();preview.textContent='從左側選擇檔案，查看問題行。';let epoch=0;
  const projectName=String(project||'').split('/').filter(Boolean).pop()||'目前專案';
  const grouped=new Map();
  for(const f of result.files||[]) {
    const parts=f.relative_path.split('/'); const fileName=parts.pop(); const folder=parts.length?parts.join('/'):'專案根目錄';
    const key=folder; if(!grouped.has(key))grouped.set(key,[]); grouped.get(key).push({...f,_fileName:fileName,_folder:folder});
  }
  for(const [folder,files] of grouped) {
    const group=document.createElement('section');group.className='health-folder-group';
    group.innerHTML=`<h4>專案資料夾：${esc(projectName)}<span>/</span>${esc(folder)}</h4>`;
    list.append(group);
    for(const f of files) {
    const button=document.createElement('button');button.className='selection-item health-file';button.dataset.healthFile=f.relative_path;
    const groupId=fileGroup(f);
    button.innerHTML=`<span class="health-file-main"><strong title="${esc(f.relative_path)}">${esc(f._fileName)}</strong><span class="health-file-meta"><small class="health-issue-count">${f.issues.length} 項待確認</small><small>最後更新時間：${esc(f.modified_at?new Date(f.modified_at).toLocaleString('zh-TW'):'示範資料')}</small></span></span><span class="health-type ${esc(groupId)}">${esc(GROUPS[groupId])}</span>`;
    button.onclick=async()=>{const id=++epoch;try {
      list.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b===button));
      const response=await bridge.call('read_memory_file',project,f.relative_path);if(id!==epoch)return;
      if(!response.ok)throw Error(response.error);
      preview.innerHTML=`<div class="panel-heading"><h3>${esc(f.relative_path)}</h3><button class="button secondary" id="healthEdit">編輯文件</button></div><div class="issue-list">${f.issues.map(i=>`<article class="issue-item"><span class="severity ${esc(i.level)}">${i.line?`第 ${i.line} 行`:'文件'}</span><div><strong>${esc(i.title)}</strong><p>${esc(i.detail)}</p></div></article>`).join('')}</div><div class="health-lines">${response.data.content.split('\n').map((line,n)=>{const found=f.issues.filter(i=>i.line&&n+1>=i.line&&n+1<=(i.end_line||i.line));return `<div class="health-line${found.length?' flagged '+esc(found[0].level):''}"><span class="line-number">${n+1}</span><span>${esc(line)||' '}</span></div>`;}).join('')}</div>`;
      preview.querySelector('#healthEdit').onclick=()=>openEditor(f.relative_path);
      preview.querySelector('.flagged')?.scrollIntoView({block:'nearest'});
    }catch(e){preview.textContent=e.message;}};
    group.append(button);
    }
  }
  if(!list.childElementCount)list.innerHTML='<p class="empty-state">本次沒有命中檢查規則；不代表文件絕對安全。</p>';
}
