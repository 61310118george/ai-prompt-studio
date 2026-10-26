let enabled = false;
export const isDeveloper = () => enabled;

export async function mountDeveloperMode({bridge, onChange}) {
  const unwrap = result => {if(!result?.ok)throw Error(result?.error||'開發人員模式操作失敗');return result.data;};
  const section = document.createElement('section');
  section.className = 'panel developer-settings';section.hidden=true;
  section.innerHTML = '<div class="panel-heading"><h3>開發人員模式</h3><button id="developerLock" class="button secondary" type="button">關閉開發人員模式</button></div><div class="developer-settings-body"><p id="developerStatus" role="status">已開啟 · 重開 App 後重新鎖定</p></div>';
  document.querySelector('#page-settings .settings-layout').append(section);
  const dialog = document.createElement('dialog');dialog.className='data-dialog developer-dialog';
  dialog.innerHTML = '<form id="developerForm"><div class="data-dialog-heading"><h3>解鎖開發人員模式</h3><button id="developerClose" class="icon-button" type="button" aria-label="關閉" title="關閉">×</button></div><label>密碼<input id="developerPassword" type="password" autocomplete="off" maxlength="128" required></label><p id="developerFormStatus" role="alert"></p><button id="developerSubmit" class="button primary" type="submit">解鎖</button></form>';
  document.body.append(dialog);
  const $ = id => document.getElementById(id);
  let clicks=0, busy=false;
  async function apply(next) {
    enabled=Boolean(next.enabled);section.hidden=!enabled;clicks=0;
    $('developerStatus').textContent='已開啟 · 重開 App 後重新鎖定';
    document.dispatchEvent(new CustomEvent('developer-mode-changed',{detail:{enabled}}));
    await onChange(enabled);
  }
  $('developerVersionTrigger').addEventListener('click',()=>{
    if(busy||dialog.open)return;
    if(enabled){lock();return;}
    if(++clicks<10)return;
    clicks=0;$('developerForm').reset();$('developerFormStatus').textContent='';
    dialog.showModal();$('developerPassword').focus();
  });
  dialog.addEventListener('close',()=>{$('developerForm').reset();clicks=0;});
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
  $('developerClose').onclick=()=>{if(!busy)dialog.close();};
  async function lock(){
    if(busy)return;busy=true;$('developerLock').disabled=true;
    try{await apply(unwrap(await bridge.call('lock_developer_mode')));}catch(error){$('developerStatus').textContent=error.message;}
    finally{busy=false;$('developerLock').disabled=false;}
  }
  $('developerLock').onclick=lock;
  $('developerForm').onsubmit=async event=>{
    event.preventDefault();if(busy)return;busy=true;$('developerSubmit').disabled=true;$('developerClose').disabled=true;
    const password=$('developerPassword').value;$('developerForm').reset();
    try{
      const next=unwrap(await bridge.call('unlock_developer_mode',password));
      dialog.close();await apply(next);
    }catch(error){$('developerFormStatus').textContent=error.message;}
    finally{busy=false;$('developerSubmit').disabled=false;$('developerClose').disabled=false;}
  };
  await apply(unwrap(await bridge.call('get_developer_status')));
}
