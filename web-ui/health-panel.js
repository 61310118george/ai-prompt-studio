import { GROUPS, fileGroup } from './file-editor.js';
export function renderHealthPanel({result,bridge,project,esc,openEditor}) {
  const list=document.querySelector('#healthFiles'), preview=document.querySelector('#healthPreview');
  const stats=[result.summary.errors,result.summary.warnings,result.summary.info,result.summary.scanned_files];
  document.querySelectorAll('#healthStats strong').forEach((n,i)=>n.textContent=stats[i]??0);
  document.querySelector('#healthScope').textContent=[result.scope_note,...(result.scan_warnings||[])].join(' ');
  list.replaceChildren();preview.innerHTML='<div class="health-preview-empty"><strong>尚未選擇檔案</strong><span>從左側選擇檔案，查看問題行。</span></div>';let epoch=0;
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
