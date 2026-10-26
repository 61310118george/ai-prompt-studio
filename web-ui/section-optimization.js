export function mountSectionOptimization({root, bridge, snapshot, onApply, trigger=null, prefix='sectionAi', writing=false}) {
  let button=trigger;
  if(!button){
  const body = root.querySelector('#promptSectionBody');
  const label = body.closest('label');
  label.htmlFor = body.id;
  const heading = document.createElement('div');
  heading.className = 'section-ai-heading wide';
  button = document.createElement('button');
  button.type = 'button'; button.id = 'sectionOptimize';
  button.className = 'button secondary compact-button'; button.textContent = 'AI 優化';
  const caption = document.createElement('label'); caption.htmlFor = body.id; caption.textContent = '項目內容';
  heading.append(caption, button); label.before(heading);
  label.firstChild.remove();
  }
  const dialog = document.createElement('dialog'); dialog.className = 'section-ai-dialog';
  dialog.innerHTML = `<form method="dialog"><div class="section-ai-heading"><h3>優化目前項目</h3><button class="button secondary compact-button" value="cancel" aria-label="關閉">×</button></div>
    <p id="sectionAiContext"></p>
    <label>希望改善什麼？<select id="sectionAiGoal"><option>讓指令更清楚且容易執行</option><option>精簡重複文字，保留必要資訊</option><option>整理條列與輸出格式</option></select></label>
    <label>內容提供給誰使用？（非必填）<input id="sectionAiAudience" maxlength="500"></label>
    <label>有哪些必須保留的條件？（非必填）<textarea id="sectionAiConstraints" rows="2" maxlength="1000"></textarea></label>
    <details><summary>本次傳送的項目內容</summary><pre id="sectionAiSource" class="code-view"></pre></details>
    <p class="field-help">確認後將標題、標籤、此項目內容與上述回答傳送至 Gemini。不傳送其他章節或專案檔。請勿包含個資或機密；可能產生 API 費用。</p>
    <button type="button" class="button primary" id="sectionAiSend">確認並送出優化</button>
    <p id="sectionAiStatus" role="status"></p>
    <section id="sectionAiReview" hidden><div class="ai-comparison"><section><h4>修改前</h4><pre id="sectionAiBefore" class="code-view"></pre></section><section><h4>修改後</h4><pre id="sectionAiAfter" class="code-view"></pre></section></div>
      <details open><summary>逐行差異</summary><pre id="sectionAiDiff" class="code-view"></pre></details>
      <button type="button" class="button primary" id="sectionAiApply">套用至目前項目</button>
    </section></form>`;
  if(writing){
    dialog.querySelector('h3').textContent='AI 輔助撰寫';
    const goal=dialog.querySelector('#sectionAiGoal');
    const answer=document.createElement('textarea');answer.id='sectionAiGoal';answer.rows=3;answer.maxLength=2000;goal.replaceWith(answer);
    dialog.querySelector('#sectionAiAudience').previousSibling.textContent='有哪些可使用的事實或素材？（非必填）';
    dialog.querySelector('#sectionAiAudience').maxLength=2000;
    dialog.querySelector('#sectionAiConstraints').maxLength=2000;
    dialog.querySelector('#sectionAiSend').textContent='確認並產生草稿';
    dialog.querySelector('#sectionAiApply').textContent='套用至此欄位';
    dialog.querySelector('.field-help').textContent='確認後將文件類型、標題、分類、此欄位原文、問題與回答送至 Gemini。其他欄位與專案檔不會傳送。請勿提供個資或機密；可能產生 API 費用。';
  }
  dialog.querySelectorAll('[id]').forEach(element=>{element.id=element.id.replace('sectionAi',prefix);});
  document.body.append(dialog);
  const $ = id => dialog.querySelector(`#${id.replace('sectionAi',prefix)}`);
  let source = null, result = null, epoch = 0, busy = false;
  const unchanged = () => JSON.stringify(source) === JSON.stringify(snapshot());
  const clearResult = () => {
    result = null; $('sectionAiReview').hidden = true;
    for(const id of ['sectionAiBefore','sectionAiAfter','sectionAiDiff'])$(id).replaceChildren();
  };
  button.onclick = () => {
    source = snapshot(); epoch++; clearResult();
    $('sectionAiContext').textContent = `標題：${source.title || '未命名'} · 標籤：${source.tags || '無'} · 項目：${source.section_title || '前言'}`;
    $('sectionAiSource').textContent = source.content;
    $('sectionAiAudience').value = ''; $('sectionAiConstraints').value = ''; $('sectionAiGoal').selectedIndex = 0;
    if(writing){$('sectionAiGoal').value='';$('sectionAiGoal').previousSibling.textContent=source.question||'希望 AI 協助撰寫什麼？';}
    $('sectionAiStatus').textContent = writing||source.content.trim() ? '' : '請先輸入項目內容。';
    $('sectionAiSend').disabled = busy || (!writing&&!source.content.trim()); dialog.showModal();
  };
  const cancel=()=>{epoch++;clearResult();};
  dialog.addEventListener('cancel',cancel);
  dialog.querySelector('form').addEventListener('submit',cancel);
  for(const id of ['sectionAiGoal','sectionAiAudience','sectionAiConstraints'])$(id).addEventListener('input',()=>{epoch++;clearResult();});
  document.addEventListener('cloud-settings-changed',()=>{epoch++;clearResult();});
  $('sectionAiSend').onclick = async () => {
    if(busy)return;
    if(writing&&!$('sectionAiGoal').value.trim()){$('sectionAiStatus').textContent='請先回答第一個問題。';return;}
    if(!unchanged()){$('sectionAiStatus').textContent='內容已變更，請關閉後重新選擇 AI 優化。';return;}
    busy = true; $('sectionAiSend').disabled = true; clearResult(); const generation = ++epoch;
    $('sectionAiStatus').textContent = '正在優化，請稍候…';
    try {
      const response = await bridge.call(writing?'draft_document_field':'optimize_prompt_section', {
        content:source.content,title:source.title,tags:source.tags,section_title:source.section_title,
        ...(writing?{document_type:source.document_type,guidance:source.guidance}:{}),
        goal:$('sectionAiGoal').value,audience:$('sectionAiAudience').value,constraints:$('sectionAiConstraints').value,consent:true,
      });
      if(generation!==epoch||!dialog.open)return;
      if(!unchanged())throw Error('內容已變更，舊結果不會套用。請重新開啟 AI 優化。');
      if(!response?.ok)throw Error(response?.error||'AI 優化失敗，原文未變更。');
      result = response.data;
      $('sectionAiBefore').textContent = source.content; $('sectionAiAfter').textContent = result.optimized;
      for(const line of result.diff.split('\n')){
        const row=document.createElement('div');row.textContent=line;
        row.className=line.startsWith('+')?'diff-add':line.startsWith('-')?'diff-remove':'';
        $('sectionAiDiff').append(row);
      }
      $('sectionAiReview').hidden = false; $('sectionAiApply').disabled = !result.changed;
      $('sectionAiStatus').textContent = result.changed ? '請確認差異後再套用，尚未變更原文。' : '目前內容不需要調整。';
    } catch(error) {if(generation===epoch)$('sectionAiStatus').textContent=error.message;}
    finally {busy=false; $('sectionAiSend').disabled=!writing&&!source?.content.trim();}
  };
  $('sectionAiApply').onclick = () => {
    if(!result)return;
    if(!unchanged()){clearResult();$('sectionAiStatus').textContent='內容已變更，請重新開啟 AI 優化。';return;}
    onApply(result.optimized); cancel();dialog.close();
  };
}
