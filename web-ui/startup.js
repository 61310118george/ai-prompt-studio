(() => {
  const status = document.getElementById('startupStatus');
  const message = document.getElementById('startupMessage');
  const retry = document.getElementById('startupRetry');
  let ready = false;
  const fail = text => {
    if(ready)return;
    clearTimeout(timer);
    window.__initError = text;
    message.textContent = text;
    retry.hidden = false;
  };
  const timer = setTimeout(() => fail('工作台載入逾時。可重新載入；若仍失敗，請確認 App 檔案完整。'), 15000);
  retry.onclick = () => {
    if(window.confirm('重新載入工作台？尚未儲存的編輯將不保留。'))window.location.reload();
  };
  window.addEventListener('app-startup-ready', () => {
    ready = true; clearTimeout(timer); status.hidden = true; window.__initError = '';
    const url = new URL(location.href); url.searchParams.delete('startup-retry');
    history.replaceState(null, '', url);
  }, {once:true});
  window.addEventListener('app-startup-error', event => fail(`工作台初始化失敗：${event.detail}`), {once:true});
  const loadModules = async () => {
    // Warm the module graph sequentially before WebKit evaluates the entry point.
    // Avoid a burst of local-server connections during a cold native launch.
    const modules = ['developer-mode', 'version', 'usage-guide', 'prompt-templates',
      'prompt-builder', 'document-catalog', 'section-optimization', 'csv-import',
      'file-description', 'file-editor', 'cloud-analysis', 'social-workspace',
      'health-panel', 'dialog-behavior', 'document-ai', 'document-builder', 'prompt-workspace'];
    for(const name of modules)await import(`./${name}.js`);
    await import('./app.js?v=4');
  };
  loadModules().catch(error => {
    window.__initCause = String(error.stack || error);
    console.error('Application module load failed', error);
    const url = new URL(location.href);
    if(!url.searchParams.has('startup-retry')) {
      clearTimeout(timer);
      message.textContent = '載入中斷，正在重新載入工作台…';
      url.searchParams.set('startup-retry', '1');
      // Only retry a failed module load, before any editor has initialized.
      setTimeout(() => location.replace(url), 300);
      return;
    }
    fail('工作台模組載入失敗，請重新載入；若仍失敗，請重新解壓完整 App。');
  });
})();
