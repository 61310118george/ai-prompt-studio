const response = result => {if(!result?.ok)throw Error(result?.error||'API 操作失敗');return result.data;};
const publishCloudStatus = status => document.dispatchEvent(new CustomEvent('cloud-status-changed',{detail:status}));

export function mountCloudSettings(bridge) {
  const panel=document.createElement('section');panel.className='panel setting-card cloud-settings';
  panel.innerHTML=`<h3>選用：AI 輔助分析</h3><p>Gemini 提供部分模型免費額度，須自行申請 API Key。這是輔助分析服務，不是工作台「預計使用的工具」。</p>
    <div class="prompt-fields"><label>分析服務<input value="Google Gemini API" disabled></label>
    <label>模型 ID<input id="cloudModel" value="gemini-3.5-flash-lite" maxlength="90" spellcheck="false"></label>
    <label id="cloudKeyLabel">API Key（只儲存在此 Mac）<input id="cloudKey" type="password" autocomplete="off" spellcheck="false" placeholder="貼上完整 Google AI Studio Key"></label>
    <p class="field-help" id="cloudKeyHelp">Key 只存在目前 macOS 使用者的 App 本機資料，不會寫入 SQLite、專案檔或 .app。複製 App 到另一台 Mac 或其他帳號時，不會帶出 Key。</p>
    <div class="inline-actions"><button class="button primary" id="cloudSave">測試並啟用</button><button class="button secondary" id="cloudClear">清除金鑰／停用</button></div>
    <p id="cloudStatus" role="status">未啟用，維持離線模式。</p></div>
    <p class="source-note">免費不代表無限使用。Gemini 免費服務可能將輸入與回覆用於產品改進；請勿傳送個資、密碼或機密。啟用計費的帳號可能產生費用，App 無法判斷你的方案，也不會替你開通付費。</p>
    <p><a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">取得 Gemini Key</a> · <a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noreferrer">免費模型與價格</a> · <a href="https://ai.google.dev/gemini-api/docs/rate-limits" target="_blank" rel="noreferrer">用量限制</a></p>
    <p class="field-help">替代方案：Groq 也有受限免費方案，本版尚未接入。查證：2026-10-07。</p>`;
  document.querySelector('.settings-layout').prepend(panel);
  const $=id=>panel.querySelector(`#${id}`);
  const status=s=>{
    const labels={connected:`已連結 Gemini（${s.model}）。${s.connection_message||''}`,error:`API 連線異常：${s.connection_message||'請確認 Key、模型與網路。'}`,checking:'正在送出測試請求…',unverified:'已讀取儲存的 Key，請按「測試並啟用」確認。',unconfigured:'未啟用，維持離線模式。'};
    $('cloudStatus').textContent=labels[s.connection]||labels.unconfigured;
    const saved=Boolean(s.key_saved);
    $('cloudKeyLabel').firstChild.textContent=saved?'API Key（本機已儲存）':'API Key（只儲存在此 Mac）';
    $('cloudKey').placeholder=saved?'本機已有 Key；留空可重新測試，貼上新 Key 可取代':'貼上完整 Google AI Studio Key';
    $('cloudKeyHelp').textContent=saved?'Key 僅存在目前 macOS 使用者的 App 本機資料，不會包進 .app 或提供給其他使用者。留空後按「測試並啟用」會重新測試；貼上新 Key 可取代目前 Key。':'Key 只存在目前 macOS 使用者的 App 本機資料，不會寫入 SQLite、專案檔或 .app。複製 App 到其他 Mac 或帳號時，對方必須自行貼上自己的 Key。';
    publishCloudStatus(s);
  };
  if(bridge.runtime!=='desktop'){
    $('cloudKey').disabled=true;$('cloudSave').disabled=true;$('cloudClear').disabled=true;
    $('cloudStatus').textContent='瀏覽器為介面示範，不接受或儲存真實金鑰。請使用桌面 App。';publishCloudStatus({connection:'unconfigured',connection_message:'瀏覽器預覽不接受或儲存 API Key。'});return;
  }
  async function configure(clear){
    $('cloudSave').disabled=true;$('cloudClear').disabled=true;
    if(!clear)status({connection:'checking',connection_message:'正在送出最小測試請求。'});
    try {status(response(await bridge.call('configure_cloud_analysis',clear?{clear:true}:{api_key:$('cloudKey').value.trim(),model:$('cloudModel').value.trim()})));document.dispatchEvent(new Event('cloud-settings-changed'));}
    catch(e){$('cloudStatus').textContent=e.message;bridge.call('get_cloud_settings').then(response).then(publishCloudStatus).catch(()=>publishCloudStatus({connection:'error',connection_message:e.message}));}
    finally{$('cloudKey').value='';$('cloudSave').disabled=false;$('cloudClear').disabled=false;}
  }
  $('cloudSave').onclick=()=>configure(false);$('cloudClear').onclick=()=>configure(true);
  bridge.call('get_cloud_settings').then(response).then(status).catch(e=>{$('cloudStatus').textContent=e.message;publishCloudStatus({connection:'error',connection_message:e.message});});
}

export function mountCloudAnalysis({root,bridge,content}){
  const box=document.createElement('details');box.className='cloud-analysis';
  box.innerHTML=`<summary>選用：請 AI 分析任務</summary><p class="field-help">使用設定中的 Gemini 分析目前草稿。只送出草稿與工具名稱，不讀取或上傳專案檔案、路徑與帳號用量。</p>
    <button class="button secondary" id="cloudAnalyze">檢查並送出分析</button><p id="cloudAnalysisStatus" role="status"></p><pre id="cloudResult" class="code-view hidden"></pre>`;
  root.append(box);const button=box.querySelector('button'),status=box.querySelector('#cloudAnalysisStatus'),result=box.querySelector('#cloudResult');let epoch=0,busy=false;
  function invalidate(){epoch++;result.textContent='';result.classList.add('hidden');status.textContent=busy?'草稿已變更，舊結果不會套用。':'';}
  root.querySelector('#usageTool').addEventListener('change',invalidate);document.addEventListener('cloud-settings-changed',invalidate);
  button.onclick=async()=>{
    if(busy)return;
    const text=content(),tool=root.querySelector('#usageTool').value;
    if(bridge.runtime!=='desktop'){status.textContent='瀏覽器不發送 API 請求；請在桌面 App 的設定啟用。';return;}
    if(tool==='local'){status.textContent='本機模型維持離線提示；若要使用雲端分析，請選擇雲端工具。';return;}
    if(!text.trim()||text.length>20000){status.textContent='請提供 1 至 20,000 字元的草稿。';return;}
    busy=true;button.disabled=true;const generation=++epoch;result.textContent='';result.classList.add('hidden');
    try{
      const settings=response(await bridge.call('get_cloud_settings'));
      if(!settings.configured)throw Error('請先到「設定 → AI 輔助分析」填寫 Gemini API Key。');
      if(generation!==epoch)return;
      if(!window.confirm(`將目前草稿（${text.length} 字元）與工具名稱送往 Google Gemini（${settings.model}）？\n\n不會上傳專案檔案。免費服務可能用於產品改進；若帳號啟用計費，可能產生費用。請先移除機密與個資。`)){status.textContent='已取消，未送出。';return;}
      status.textContent='AI 分析中，最長約 35 秒…';
      const data=response(await bridge.call('analyze_with_ai',{content:text,tool,consent:true}));
      bridge.call('get_cloud_settings').then(response).then(publishCloudStatus).catch(()=>{});
      if(generation!==epoch||text!==content())return;
      result.textContent=data.text;result.classList.remove('hidden');status.textContent=`${data.provider} · ${data.model}。${data.note}${data.truncated?' 回應已達長度限制，可能不完整。':''}`;
    }catch(e){if(generation===epoch)status.textContent=e.message;bridge.call('get_cloud_settings').then(response).then(publishCloudStatus).catch(()=>{});}
    finally{busy=false;button.disabled=false;}
  };
  return invalidate;
}
