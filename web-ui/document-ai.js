import { DOCUMENT_FIELDS } from './document-catalog.js';

export function mountDocumentAi({bridge, snapshot, onApply, status, busyChanged}) {
  const dialog=document.createElement('dialog');
  dialog.className='section-ai-dialog document-ai-dialog';
  dialog.innerHTML=`<form method="dialog"><div class="section-ai-heading"><h3 id="documentAiHeading"></h3><button class="button secondary compact-button" value="cancel" aria-label="關閉">×</button></div>
    <h4>AI 的理解（請核對）</h4><ul id="documentAiUnderstanding"></ul>
    <div id="documentAiQuestions" class="document-ai-questions"></div>
    <p class="field-help">回答將傳送至 Gemini。若理解不符請直接更正；尚不確定可填「待確認」。請勿提供機密或個資，可能產生 API 費用。</p>
    <button type="button" class="button primary" id="documentAiCompose">根據回答產生內容</button>
    <p id="documentAiStatus" role="status"></p>
    <section id="documentAiReview" hidden><h4 tabindex="-1" id="documentAiReviewHeading">套用前確認</h4><div id="documentAiComparison"></div><button type="button" class="button primary" id="documentAiApply">套用至表單</button></section></form>`;
  document.body.append(dialog);
  const $=id=>dialog.querySelector(`#${id}`);
  const response=r=>{if(!r?.ok)throw Error(r?.error||'AI 操作失敗，原文未變更。');return r.data;};
  let source=null, request=null, review=null, result=null, epoch=0, busy=false;
  const unchanged=()=>JSON.stringify(source)===JSON.stringify(snapshot());
  const setBusy=value=>{busy=value;busyChanged(value);$('documentAiCompose').disabled=value;};
  const clearResult=()=>{result=null;$('documentAiReview').hidden=true;$('documentAiComparison').replaceChildren();};
  // Invalidate synchronously: WebKit may deliver a close event after the next request starts.
  const cancel=()=>{epoch++;clearResult();};
  dialog.addEventListener('cancel',cancel);
  dialog.querySelector('form').addEventListener('submit',cancel);
  document.addEventListener('cloud-settings-changed',()=>{epoch++;clearResult();status.textContent='AI 設定已變更，請重新分析。';});
  const start=async(mode,fieldId='')=>{
    if(busy)return;
    source=snapshot();
    if(!source.title.trim()){status.textContent='請先輸入標題。';return;}
    const content=source.fields[fieldId]||'';
    if(mode==='revise'&&!content.trim()){status.textContent='請先填寫要修正的欄位內容。';return;}
    const disclosure=mode==='revise'?'標題、標籤與這一欄的內容':'標題、標籤與文件類型';
    if(!window.confirm(`將${disclosure}傳送至 Gemini，分析理解並產生確認問題？不傳送其他文件，可能產生 API 費用。`))return;
    request={mode,field_id:fieldId,title:source.title,tags:source.tags,document_type:source.document_type,
      guidance:source.guidance,content:mode==='revise'?content:'',consent:true};
    const generation=++epoch;clearResult();setBusy(true);status.textContent='AI 正在分析理解與確認問題…';
    try{
      const data=response(await bridge.call('clarify_document',request));
      if(generation!==epoch)return;
      if(!unchanged())throw Error('內容已變更，已捨棄舊分析，請重新點擊 AI。');
      review=data;
      $('documentAiHeading').textContent=mode==='revise'?'AI 修正：確認理解':'AI 輔助撰寫：確認需求';
      $('documentAiUnderstanding').replaceChildren();
      for(const text of data.understanding){const li=document.createElement('li');li.textContent=text;$('documentAiUnderstanding').append(li);}
      $('documentAiQuestions').replaceChildren();
      data.questions.forEach((question,index)=>{
        const label=document.createElement('label');label.textContent=`${index+1}. ${question}`;
        const input=document.createElement('textarea');input.rows=2;input.maxLength=2000;input.dataset.aiAnswer=String(index);
        input.oninput=()=>{epoch++;clearResult();$('documentAiStatus').textContent='回答已變更，請重新產生內容。';};label.append(input);$('documentAiQuestions').append(label);
      });
      $('documentAiStatus').textContent='';status.textContent='';dialog.showModal();
    }catch(error){if(generation===epoch)status.textContent=error.message;}
    finally{setBusy(false);}
  };
  $('documentAiCompose').onclick=async()=>{
    if(busy)return;
    if(!unchanged()){$('documentAiStatus').textContent='原文已變更，請關閉後重新分析。';return;}
    const answers=[...dialog.querySelectorAll('[data-ai-answer]')].map(input=>input.value.trim());
    if(answers.some(answer=>!answer)){$('documentAiStatus').textContent='請逐題回答；尚不確定可填「待確認」。';return;}
    const generation=++epoch;clearResult();setBusy(true);$('documentAiStatus').textContent='正在根據回答產生內容…';
    try{
      const data=response(await bridge.call('compose_document',{...request,clarification:review,answers}));
      if(generation!==epoch||!dialog.open)return;
      if(!unchanged())throw Error('原文已變更，舊結果不會套用。');
      result=data.fields;
      for(const [key,value] of Object.entries(result)){
        const section=document.createElement('section'), heading=document.createElement('h4');
        heading.textContent=DOCUMENT_FIELDS[source.document_type].find(field=>field.id===key).label;
        const columns=document.createElement('div');columns.className='ai-comparison';
        for(const [label,text] of [['修改前',source.fields[key]||'（空白）'],['修改後',value]]){
          const column=document.createElement('div'), caption=document.createElement('strong'), body=document.createElement('pre');
          caption.textContent=label;body.textContent=text;body.className='code-view';column.append(caption,body);columns.append(column);
        }
        section.append(heading,columns);$('documentAiComparison').append(section);
      }
      $('documentAiReview').hidden=false;$('documentAiStatus').textContent='尚未修改原文，請確認前後內容再套用。';
      requestAnimationFrame(()=>{
        if(generation!==epoch||!dialog.open||!result)return;
        const heading=$('documentAiReviewHeading');
        heading.focus({preventScroll:true});
        const offset=heading.getBoundingClientRect().top-dialog.getBoundingClientRect().top;
        dialog.scrollTo({top:dialog.scrollTop+offset-20,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
      });
    }catch(error){if(generation===epoch)$('documentAiStatus').textContent=error.message;}
    finally{setBusy(false);}
  };
  $('documentAiApply').onclick=()=>{
    if(!result)return;
    if(!unchanged()){clearResult();$('documentAiStatus').textContent='原文已變更，請重新分析。';return;}
    onApply(result);cancel();dialog.close();status.textContent='已套用至表單；請建立提示詞更新預覽並儲存。';
  };
  return {start};
}
