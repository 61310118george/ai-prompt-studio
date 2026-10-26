import { isDeveloper } from './developer-mode.js';
const unwrap = value => { if (!value?.ok) throw Error(value?.error || '社群操作失敗'); return value.data; };
const names = {facebook:'Facebook', instagram:'Instagram', threads:'Threads'};
const labels = {views:'觀看',post_media_view:'觀看',reach:'觸及',likes:'按讚',reactions:'反應',comments:'留言',replies:'回覆',shares:'分享',saved:'收藏',reposts:'轉發',quotes:'引用'};
const statusNames = {connected:'已連接',disconnected:'已中斷',expired:'需重新授權',partial:'部分指標未提供',permission:'權限不足',rate_limited:'平台限流',error:'連線異常'};

export function mountSocialSettings({bridge, esc}) {
  const section = document.createElement('section'); section.className = 'panel social-settings';
  section.hidden=true;
  section.innerHTML = `<h3>社群帳號</h3><div class="social-config"><label>授權服務網址<input id="socialService" type="url" placeholder="https://your-service.example.com"></label><label>連線碼<input id="socialCode" type="password" autocomplete="off" placeholder="部署時設定的連線碼"></label></div><div class="data-toolbar"><button class="button secondary" id="socialConfigure">儲存連線設定</button><button class="button primary" id="socialFacebook">連接 Facebook／IG</button><button class="button primary" id="socialThreads">連接 Threads</button></div><p id="socialSettingStatus" role="status"></p><div id="socialCandidates"></div><div id="socialAccounts"></div>`;
  document.querySelector('#page-settings .settings-layout').append(section);
  const $ = id => section.querySelector('#' + id);
  let loginGeneration = 0;
  const run = fn => async event => { if(!isDeveloper())return;const button = event?.currentTarget; if (button) button.disabled = true; try { await fn(); } catch (error) { $('socialSettingStatus').textContent = error.message; } finally { if (button) button.disabled = false; } };
  async function refresh(initial=false) {
    if(!isDeveloper())return;
    const generation=loginGeneration;
    const data = unwrap(await bridge.call('get_social_settings'));
    if(!isDeveloper()||generation!==loginGeneration)return;
    if (initial) $('socialService').value = data.service_url;
    $('socialAccounts').innerHTML = data.accounts.map(account=>`<div class="social-account"><div><strong>${names[account.platform]} · ${esc(account.name)}</strong><p>${esc(statusNames[account.status] || account.status)}${account.synced_at?' · '+esc(new Date(account.synced_at).toLocaleString()):''}</p></div><div class="data-toolbar"><button class="button secondary compact-button" data-disconnect="${account.platform}" ${!account.connected?'disabled':''}>解除連線</button><button class="button secondary compact-button" data-clear="${account.platform}">清除歷史數據</button></div></div>`).join('') || '<p>尚未連接社群帳號</p>';
    section.querySelectorAll('[data-disconnect]').forEach(button=>button.onclick=run(async()=>{
      if (!confirm('解除此帳號連線？本機歷史數據會保留。')) return;
      unwrap(await bridge.call('disconnect_social',button.dataset.disconnect)); await refresh(); document.dispatchEvent(new Event('social-data-changed'));
    }));
    section.querySelectorAll('[data-clear]').forEach(button=>button.onclick=run(async()=>{
      if (!confirm('刪除此平台的本機貼文、指標與所有社群 AI 分析紀錄？')) return;
      unwrap(await bridge.call('clear_social_data',button.dataset.clear)); await refresh(); document.dispatchEvent(new Event('social-data-changed'));
    }));
  }
  $('socialConfigure').onclick = run(async()=>{
    unwrap(await bridge.call('configure_social',$('socialService').value,$('socialCode').value)); $('socialCode').value=''; loginGeneration++;
    $('socialSettingStatus').textContent='連線設定已儲存。'; $('socialCandidates').replaceChildren();
  });
  async function login(provider) {
    const generation = ++loginGeneration;
    $('socialCandidates').replaceChildren(); $('socialSettingStatus').textContent='正在開啟官方登入頁…';
    unwrap(await bridge.call('begin_social_login',provider)); $('socialSettingStatus').textContent='請在系統瀏覽器完成登入，完成後回到此視窗。';
    const poll = async () => {
      if (generation !== loginGeneration) return;
      try {
        const data = unwrap(await bridge.call('poll_social_login'));
        if (generation !== loginGeneration) return;
        if (data.status !== 'ready') { setTimeout(poll,2500); return; }
        const platforms=[...new Set(data.accounts.map(a=>a.platform))];
        $('socialCandidates').innerHTML=platforms.map(platform=>`<label>${names[platform]}<select data-account-platform="${platform}"><option value="">不連接</option>${data.accounts.filter(a=>a.platform===platform).map(a=>`<option value="${esc(a.key)}">${esc(a.name)} (${esc(a.account_id)})</option>`).join('')}</select></label>`).join('')+'<button class="button primary" id="socialSelect">連接所選帳號</button>';
        $('socialSettingStatus').textContent='請選擇公司帳號。';
        $('socialSelect').onclick=run(async()=>{
          const keys=[...section.querySelectorAll('[data-account-platform]')].map(s=>s.value).filter(Boolean);
          unwrap(await bridge.call('select_social_accounts',keys)); $('socialCandidates').replaceChildren(); $('socialSettingStatus').textContent='帳號已連接，可到提示詞工作台同步數據。'; await refresh(); document.dispatchEvent(new Event('social-data-changed'));
        });
      } catch(error) { $('socialSettingStatus').textContent=error.message; }
    };
    setTimeout(poll,1500);
  }
  $('socialFacebook').onclick=run(()=>login('facebook'));
  $('socialThreads').onclick=run(()=>login('threads'));
  document.addEventListener('developer-mode-changed',()=>{
    loginGeneration++;section.hidden=!isDeveloper();
    $('socialCode').value='';$('socialService').value='';$('socialCandidates').replaceChildren();$('socialAccounts').replaceChildren();$('socialSettingStatus').textContent='';
    if(isDeveloper())refresh(true).catch(error=>$('socialSettingStatus').textContent=error.message);
  });
  document.addEventListener('social-data-changed',()=>refresh().catch(error=>$('socialSettingStatus').textContent=error.message));
}

export function mountSocialWorkspace({root,bridge,esc,content,onApply}) {
  const tabs=document.createElement('div'); tabs.className='workspace-tabs'; tabs.setAttribute('role','tablist');
  tabs.innerHTML='<button type="button" role="tab" aria-selected="true" id="promptEditorTab" aria-controls="promptEditorView">提示詞編輯</button><button type="button" role="tab" aria-selected="false" id="socialDataTab" aria-controls="socialDataView">社群數據</button>';
  root.querySelector('.page-intro').after(tabs);
  tabs.hidden=true;
  const editor=root.querySelector('.prompt-layout'); editor.id='promptEditorView'; editor.setAttribute('role','tabpanel');
  const section=document.createElement('section'); section.id='socialDataView'; section.hidden=true; section.setAttribute('role','tabpanel');
  section.innerHTML=`<div class="data-toolbar"><label>平台<select id="socialPlatform"><option value="facebook">Facebook</option><option value="instagram">Instagram</option><option value="threads">Threads</option></select></label><label>內容類型<select id="socialType"><option value="">全部</option></select></label><label>排序<select id="socialSort"><option value="published_at">發布時間</option><option value="views">觀看次數</option></select></label><button class="button secondary" id="socialSync">同步最近 30 天</button><button class="button primary" id="socialPreview">依數據優化提示詞</button></div><p id="socialDataStatus" role="status"></p><div id="socialPosts" class="data-table-scroll"></div><section id="marketingResult" hidden><h3>社群數據優化</h3><div id="marketingAdvice"></div><div class="marketing-comparison"><div><h4>優化前</h4><pre id="marketingBefore"></pre></div><div><h4>優化後</h4><pre id="marketingAfter"></pre></div></div><details><summary>逐行差異</summary><pre id="marketingDiff"></pre></details><button class="button primary" id="marketingApply">套用至提示詞草稿</button></section>`;
  root.append(section);
  const dialog=document.createElement('dialog'); dialog.className='data-dialog';
  dialog.innerHTML='<form method="dialog" class="data-dialog-heading"><h3>送往 Gemini 的內容</h3><button class="icon-button" title="關閉" aria-label="關閉">×</button></form><p>包含目前提示詞與選取貼文的文字、連結及數據。</p><pre id="marketingPayload"></pre><p id="marketingPreviewStatus" role="status"></p><button type="button" class="button primary" id="marketingSend">確認並送出優化</button>';
  root.append(dialog);
  const $=id=>root.querySelector('#'+id);
  let rows=[], selected=new Set(), epoch=0, preview=null, result=null, busy=false, lastContent=content(), loadGeneration=0;
  function invalidate(){epoch++;preview=null;result=null;$('marketingResult').hidden=true;$('marketingSend').disabled=true;}
  dialog.addEventListener('cancel',invalidate);
  dialog.querySelector('form').addEventListener('submit',invalidate);
  const watch=()=>{if(lastContent!==content()){lastContent=content();invalidate();}};
  const run=fn=>async()=>{if(busy||!isDeveloper())return;busy=true;['socialSync','socialPreview','marketingSend','marketingApply'].forEach(id=>$(id).disabled=true);try{await fn();}catch(error){$('socialDataStatus').textContent=error.message;$('marketingPreviewStatus').textContent=error.message;}finally{busy=false;['socialSync','socialPreview','marketingApply'].forEach(id=>$(id).disabled=false);$('marketingSend').disabled=!preview;}};
  function showEditor(){editor.hidden=false;section.hidden=true;$('promptEditorTab').setAttribute('aria-selected','true');$('socialDataTab').setAttribute('aria-selected','false');}
  $('promptEditorTab').onclick=showEditor;
  $('socialDataTab').onclick=()=>{if(!isDeveloper())return;editor.hidden=true;section.hidden=false;$('promptEditorTab').setAttribute('aria-selected','false');$('socialDataTab').setAttribute('aria-selected','true');load().catch(error=>$('socialDataStatus').textContent=error.message);};
  function render(){
    const filtered=rows.filter(row=>!$('socialType').value||row.media_type===$('socialType').value);
    filtered.sort((a,b)=>$('socialSort').value==='views'?((b.metrics.views??b.metrics.post_media_view??-1)-(a.metrics.views??a.metrics.post_media_view??-1)):b.published_at.localeCompare(a.published_at));
    $('socialPosts').innerHTML=filtered.length?`<table class="data-table social-table"><thead><tr><th>參考</th><th>貼文</th><th>類型／時間</th><th>累積指標</th></tr></thead><tbody>${filtered.map(row=>`<tr><td><input type="checkbox" data-snapshot="${row.snapshot_id}" aria-label="選取貼文 ${esc(row.post_id)}" ${selected.has(row.snapshot_id)?'checked':''}></td><td><details><summary>${esc(row.content.slice(0,100)||'無文字貼文')}</summary><pre>${esc(row.content)}</pre></details>${/^https:\/\//.test(row.permalink)?`<a target="_blank" rel="noreferrer" href="${esc(row.permalink)}">查看貼文</a>`:''}<small>快照 #${row.snapshot_id}</small></td><td>${esc(row.media_type)}<br>${esc(new Date(row.published_at).toLocaleString())}<small>同步 ${esc(new Date(row.captured_at).toLocaleString())}</small></td><td>${Object.entries(row.metrics).map(([key,value])=>`<div>${esc(labels[key]||key)}：${value===null?'未提供':Number(value).toLocaleString()}</div>`).join('')}${row.warnings.length?'<details><summary>指標限制</summary>'+esc(row.warnings.join('；'))+'</details>':''}</td></tr>`).join('')}</tbody></table>`:'<p class="empty-state">尚無貼文數據，請先在設定連接帳號並同步。</p>';
    section.querySelectorAll('[data-snapshot]').forEach(input=>input.onchange=()=>{const id=Number(input.dataset.snapshot);if(input.checked&&selected.size>=10){input.checked=false;$('socialDataStatus').textContent='每次最多選擇 10 則參考貼文。';return;}if(input.checked)selected.add(id);else selected.delete(id);invalidate();});
  }
  async function load(){if(!isDeveloper())return;const generation=++loadGeneration;const platform=$('socialPlatform').value;const data=unwrap(await bridge.call('list_social_posts',platform));if(!isDeveloper()||generation!==loadGeneration)return;rows=data;selected=new Set();invalidate();$('socialType').innerHTML='<option value="">全部</option>'+[...new Set(rows.map(r=>r.media_type))].map(type=>`<option>${esc(type)}</option>`).join('');render();}
  $('socialPlatform').onchange=()=>load().catch(e=>$('socialDataStatus').textContent=e.message);
  $('socialType').onchange=()=>{selected.clear();invalidate();render();};$('socialSort').onchange=render;
  $('socialSync').onclick=run(async()=>{invalidate();$('socialDataStatus').textContent='同步中…';const data=unwrap(await bridge.call('sync_social',$('socialPlatform').value));await load();$('socialDataStatus').textContent=`同步 ${data.count} 則 · ${data.period}${data.limited?' · 已達讀取上限':''}${data.warnings.length?' · 部分指標未提供':''}`;document.dispatchEvent(new Event('social-data-changed'));});
  $('socialPreview').onclick=run(async()=>{watch();const generation=epoch;const data=unwrap(await bridge.call('preview_marketing',content(),[...selected]));if(!isDeveloper()||generation!==epoch)return;preview=data;$('marketingPayload').textContent=JSON.stringify({提示詞:preview.content,參考貼文:preview.evidence},null,2);$('marketingPreviewStatus').textContent=preview.evidence.length<5?'樣本少於 5 則，建議僅作為待驗證假設。':'';dialog.showModal();});
  $('marketingSend').onclick=run(async()=>{
    const generation=epoch, currentPreview=preview;preview=null;$('marketingPreviewStatus').textContent='AI 分析與優化中…';
    const data=unwrap(await bridge.call('optimize_marketing',currentPreview.preview_id,true));
    if(generation!==epoch||currentPreview.content!==content())throw Error('草稿或數據已變更，請重新分析。');
    result=data;dialog.close();$('marketingResult').hidden=false;
    $('marketingAdvice').innerHTML=['observations','suggestions'].map(field=>`<h4>${field==='observations'?'數據觀察':'建議調整'}</h4><ul>${data[field].map(item=>`<li>${esc(item.text)} <small>依據：${item.snapshot_ids.map(id=>'#'+id).join('、')}</small></li>`).join('')}</ul>`).join('');
    $('marketingBefore').textContent=data.original;$('marketingAfter').textContent=data.optimized;
    $('marketingDiff').innerHTML=data.diff.split('\n').map(line=>`<span class="${line.startsWith('+')?'diff-added':line.startsWith('-')?'diff-removed':''}">${esc(line)}</span>`).join('\n');
    $('socialDataStatus').textContent='優化完成，請確認差異後套用。';
  });
  $('marketingApply').onclick=run(async()=>{watch();if(!result)throw Error('結果已失效，請重新分析。');const generation=epoch;const data=unwrap(await bridge.call('apply_marketing',result.run_id,content(),[...selected]));if(!isDeveloper()||generation!==epoch)return;onApply(data.content);invalidate();showEditor();});
  document.addEventListener('social-data-changed',()=>{invalidate();load().catch(e=>$('socialDataStatus').textContent=e.message);});
  document.addEventListener('cloud-settings-changed',invalidate);
  document.addEventListener('developer-mode-changed',()=>{
    tabs.hidden=!isDeveloper();
    if(!isDeveloper()){
      loadGeneration++;invalidate();rows=[];selected.clear();dialog.close();showEditor();
      for(const id of ['socialPosts','marketingPayload','marketingAdvice','marketingBefore','marketingAfter','marketingDiff','socialDataStatus','marketingPreviewStatus'])$(id).replaceChildren();
    }
  });
  return watch;
}
