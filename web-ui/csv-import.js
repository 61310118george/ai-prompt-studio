const unwrap = value => { if (!value?.ok) throw Error(value?.error || '匯入失敗'); return value.data; };

export function mountCsvImport({root, bridge, scope, refreshed, esc, toast}) {
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'button secondary compact-button'; button.textContent = '匯入 CSV';
  root.querySelector('.prompt-file-actions').append(button);
  const dialog = document.createElement('dialog'); dialog.className = 'data-dialog';
  dialog.innerHTML = `<form method="dialog" class="data-dialog-heading"><h3>匯入 CSV</h3><button class="icon-button" aria-label="關閉" title="關閉">×</button></form>
    <div class="data-toolbar"><label>匯入類型<select id="csvKind"><option value="prompts">提示詞卡片</option><option value="templates">標籤模板</option></select></label><button type="button" class="button secondary" id="csvExample">匯出範例 CSV</button><button type="button" class="button primary" id="csvChoose">選擇 CSV</button></div>
    <p id="csvStatus" role="status"></p><div id="csvRows" class="data-table-scroll"></div>
    <div class="data-toolbar"><label class="inline-check"><input type="checkbox" id="csvUpdate">更新同名項目</label><button type="button" class="button primary" id="csvCommit" disabled>確認匯入</button></div>`;
  root.append(dialog);
  const $ = id => dialog.querySelector('#' + id);
  let preview = null, busy = false;
  const selected = () => [...dialog.querySelectorAll('[data-csv-row]:checked')].map(input => Number(input.dataset.csvRow));
  const buttons = () => { ['csvChoose','csvExample','csvKind','csvUpdate'].forEach(id => $(id).disabled = busy); $('csvCommit').disabled = busy || !preview || !selected().length; };
  const run = fn => async () => { if (busy) return; busy = true; buttons(); try { await fn(); } catch (error) { $('csvStatus').textContent = error.message; } finally { busy = false; buttons(); } };
  button.onclick = () => dialog.showModal();
  $('csvKind').onchange = () => { preview = null; $('csvRows').replaceChildren(); $('csvStatus').textContent = ''; buttons(); };
  $('csvExample').onclick = run(async () => { const data = unwrap(await bridge.call('export_csv_example', $('csvKind').value)); if (data) $('csvStatus').textContent = `已匯出 ${data.filename}`; });
  $('csvChoose').onclick = run(async () => {
    preview = null; $('csvRows').replaceChildren();
    const data = unwrap(await bridge.call('preview_csv_import', $('csvKind').value, scope()));
    if (!data) { $('csvStatus').textContent = '已取消選檔'; return; }
    preview = data;
    $('csvStatus').textContent = `${data.filename} · ${data.rows.length} 筆 · ${data.rows.filter(row=>row.errors.length).length} 筆有錯誤 · ${data.kind === 'templates' ? '全 App 標籤模板' : '目前提示詞範本庫'}`;
    $('csvRows').innerHTML = `<table class="data-table"><thead><tr><th>選取</th><th>CSV 行</th><th>內容</th><th>狀態</th></tr></thead><tbody>${data.rows.map(row=>`<tr><td><input type="checkbox" aria-label="匯入第 ${row.line} 行" data-csv-row="${row.index}" ${row.errors.length?'disabled':'checked'}></td><td>${row.line}</td><td><strong>${esc(row.data.title || row.data.tag)}</strong><details><summary>${esc(row.data.group || '標籤模板')}</summary><pre>${esc(Object.entries(row.data).map(([key,value])=>`${key}: ${value}`).join('\n'))}</pre></details></td><td>${esc(row.errors.join('；') || (row.duplicate?'同名項目，預設略過':'新增'))}</td></tr>`).join('')}</tbody></table>`;
    $('csvRows').onchange = buttons;
  });
  $('csvCommit').onclick = run(async () => {
    if (scope() !== preview.scope) throw Error('範本庫已切換，請重新選檔。');
    const result = unwrap(await bridge.call('commit_csv_import', {preview_id:preview.preview_id, project_path:scope(), indices:selected(), update:$('csvUpdate').checked}));
    preview = null; $('csvRows').replaceChildren();
    const message = `新增 ${result.created} 筆、更新 ${result.updated} 筆、略過 ${result.skipped} 筆。`;
    $('csvStatus').textContent = message; toast(message); await refreshed();
  });
}
