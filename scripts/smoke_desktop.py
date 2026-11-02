"""Exercise the real macOS WebKit bridge with an isolated, disposable project."""
import json
import io
import tempfile
import time
import os
import shutil
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

import webview

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.desktop_api import DesktopApi
from ai_memory_app.services.cloud_advisor import CloudAdvisor
from ai_memory_app.services.social_data import SocialData
from datetime import datetime, timezone


class MemoryCredentialStore:
    def __init__(self):
        self.value = ''

    def load(self):
        return self.value

    def save(self, secret):
        self.value = secret

    def clear(self):
        self.value = ''


def main():
    root = Path(__file__).resolve().parents[1]
    result = {}
    with tempfile.TemporaryDirectory(prefix="prompt-studio-smoke-") as folder:
        temp = Path(folder)
        project = temp / "project"
        project.mkdir()
        (project / 'AGENTS.md').write_text('# 規則\n\n- 保留所有必要條件。\n', encoding='utf-8')
        (project / 'notes.md').write_text('# 測試資料\npassword: example-only\n', encoding='utf-8')
        skill = project / '.agents' / 'skills' / 'review' / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('# Review skill\nRead the project documentation.', encoding='utf-8')
        db = temp / "test.sqlite3"
        initialize_database(db)

        class FixtureApi(DesktopApi):
            def export_document_project(self, title, documents):
                original = self._window
                self._window = SimpleNamespace(create_file_dialog=lambda *args, **kwargs: (str(temp),))
                try:
                    return super().export_document_project(title, documents)
                finally:
                    self._window = original

            def preview_csv_import(self, kind, project_path):
                data = self._csv_import.preview(self._csv_import.example(kind).encode(), kind, self._prompt_scope(project_path))
                return self._response({**data, 'filename': 'desktop-test.csv'})

            def choose_project_root(self):
                return self.set_project_root(str(project))

            def import_prompt_file(self):
                return self._response({"name": "本機匯入", "filename": "本機匯入.md", "path": str(temp / "本機匯入.md"), "content": "# 本機提示詞\n\n請保留限制。\n\n## 核心流程\n\n先確認需求。\n\n## 主導航\n\n- 專案\n- 設定\n"})

            def export_prompt_file(self, title, content):
                target = temp / "native-export.md"
                self._atomic_write(target, content)
                return self._response({"filename": target.name, "path": str(target), "bytes": len(content.encode("utf-8"))})

        api = FixtureApi(MemoryRepository(db), backup_root=temp / "backups")
        api._cloud_advisor = CloudAdvisor(MemoryCredentialStore())
        class TestSecrets:
            def get(self, key): return 'test-social-token'
            def set(self, key, value): pass
            def delete(self, key): pass

        def fake_social(url, token, params=None, payload=None):
            if url.endswith('/threads'):
                return {'data': [{'id': '123', 'text': '整復店的日常保健分享', 'timestamp': datetime.now(timezone.utc).isoformat(), 'media_type': 'TEXT'}]}
            return {'data': [{'name': 'views', 'values': [{'value': 100}]}, {'name': 'likes', 'values': [{'value': 8}]}]}
        api._social = SocialData(db, TestSecrets(), fake_social)
        api._social._candidates = (time.monotonic(), [{'platform':'threads','account_id':'123','name':'桌面測試公司','access_token':'test-social-token'}])
        api._social.select_accounts(['0'])
        # No real network or key: exercise real WebKit bridge with a stub transport.
        def fake_cloud(req, **kwargs):
            payload = json.loads(req.data)
            instruction = payload.get('systemInstruction', {}).get('parts', [{}])[0].get('text', '')
            if '社群行銷提示詞編輯器' in instruction:
                evidence = json.loads(payload['contents'][0]['parts'][0]['text'])['social_evidence']
                refs = [evidence[0]['snapshot_id']]
                text = json.dumps({'observations':[{'text':'樣本不足，先測試開頭。','snapshot_ids':refs}],'suggestions':[{'text':'保留事實並加入清楚的行動呼籲。','snapshot_ids':refs}],'optimized':'# 社群貼文任務\n\n保留事實，以繁體中文撰寫貼文並加入行動呼籲。'},ensure_ascii=False)
            elif '文件理解確認助手' in instruction:
                text = json.dumps({'understanding':['你希望整理已確認的需求。'], 'questions':['是否理解正確？請補充範圍。', '有哪些限制需要保留？']}, ensure_ascii=False)
            elif '確認後的文件撰寫助手' in instruction:
                fields = json.loads(payload['contents'][0]['parts'][0]['text'])['field_schema']
                text = json.dumps({'fields': {key: '協助整理已確認需求，不補造未知事實。' for key in fields}}, ensure_ascii=False)
            elif '文件欄位撰寫助手' in instruction:
                text = '協助整理已確認需求，不補造未知事實。'
            elif 'Markdown 項目編輯器' in instruction:
                text = '以繁體中文整理重點，保留原有事實。'
            elif '提示詞優化編輯器' in instruction:
                text = '## 任務\n\n- 請保留重要限制。\n- 使用繁體中文。'
            elif '任務分析助手' in instruction:
                text = '1. 任務難度：中\n2. 預估 Token：500–800\n3. 建議修正：先確認範圍 <script>literal</script>\n4. 方案建議：先使用現有額度'
            else:
                text = 'OK'
            return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [{'text': text}]}}]}).encode())

        api._cloud_advisor._open = fake_cloud
        ui_root = Path(os.environ.get('PROMPT_STUDIO_SMOKE_UI_ROOT', root / 'web-ui')).resolve()
        startup_failure = '--startup-failure' in sys.argv
        if startup_failure:
            broken_ui = db.parent / 'broken-ui'
            shutil.copytree(ui_root, broken_ui, ignore=shutil.ignore_patterns('app.js'))
            ui_root = broken_ui
        window = webview.create_window("Prompt Studio isolated smoke test", str(ui_root / "index.html"), js_api=api, width=1440, height=1000)
        api.attach_window(window)

        def exercise():
            try:
                deadline = time.monotonic() + 60
                if startup_failure:
                    while time.monotonic() < deadline:
                        if window.evaluate_js("Boolean(window.__initError && document.querySelector('#startupRetry')?.hidden === false)"):
                            if not window.evaluate_js("new URL(location.href).searchParams.get('startup-retry') === '1'"):
                                raise RuntimeError('Startup failure did not attempt one bounded reload')
                            result.update(passed=True, startup_failure_visible=True)
                            return
                        time.sleep(.1)
                    raise RuntimeError('Missing module left a silent blank workspace')
                while not window.evaluate_js("Boolean(document.querySelector('#promptSave'))"):
                    if time.monotonic() > deadline or window.evaluate_js("Boolean(window.__initError)"):
                        diagnostics = window.evaluate_js("""
                        ({
                          readyState: document.readyState,
                          location: location.href,
                          title: document.title,
                          importError: window.__initError || '',
                          importCause: window.__initCause || '',
                          bodyText: document.body?.innerText?.slice(0, 500) || '',
                          promptRoot: document.querySelector('#page-prompts')?.innerHTML?.slice(0, 500) || '',
                        })
                        """)
                        assets = {}
                        for asset in ui_root.glob('*.js'):
                            try:
                                url = urllib.parse.urljoin(diagnostics['location'], asset.name)
                                with urllib.request.urlopen(url, timeout=5) as reply:
                                    assets[asset.name] = [reply.status, reply.headers.get('Content-Type'), len(reply.read())]
                            except Exception as error:
                                assets[asset.name] = str(error)
                        diagnostics['assets'] = assets
                        raise RuntimeError(f"UI did not initialize: {diagnostics}")
                    time.sleep(.1)
                window.evaluate_js("""
                (async () => {
                  const waitFor = async (condition) => { for(let i=0;i<200;i++){if(await condition()) return; await new Promise(r=>setTimeout(r,50));} throw Error('Timed out waiting for UI'); };
                  let stage='initial load';
                  const set = (id, value) => {const input=document.getElementById(id);input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}));};
                  const dragCard = async (card, targetGroup, pointerId) => {
                    const from=card.getBoundingClientRect();
                    card.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId,pointerType:'mouse',button:0,clientX:from.left+24,clientY:from.top+24}));
                    targetGroup.scrollIntoView({block:'center'});await new Promise(r=>setTimeout(r,60));
                    const to=targetGroup.getBoundingClientRect(),x=to.left+Math.min(80,to.width/2),y=to.top+Math.min(70,to.height/2);
                    window.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,pointerId,pointerType:'mouse',buttons:1,clientX:x,clientY:y}));
                    await new Promise(r=>setTimeout(r,60));
                    window.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId,pointerType:'mouse',button:0,clientX:x,clientY:y}));
                  };
                  const dragCardBefore = async (card, targetCard, pointerId) => {
                    const from=card.getBoundingClientRect(),to=targetCard.getBoundingClientRect();
                    card.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId,pointerType:'mouse',button:0,clientX:from.left+12,clientY:from.top+12}));
                    window.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,pointerId,pointerType:'mouse',buttons:1,clientX:to.left+40,clientY:to.top+2}));
                    await new Promise(r=>setTimeout(r,60));
                    window.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId,pointerType:'mouse',button:0,clientX:to.left+40,clientY:to.top+2}));
                  };
                  try {
                    stage='personal library ready';
                    await waitFor(()=>document.querySelector('[data-template-card="develop-feature"]'));
                    await waitFor(()=>document.getElementById('developerForm'));
                    await waitFor(()=>document.getElementById('startupStatus').hidden);
                    if(document.querySelectorAll('#navList .nav-button').length!==3)throw Error('Default navigation should contain three entries');
                    if(!document.querySelector('.usage-guide').hidden)throw Error('Whole-prompt AI exposed before unlock');
                    if(!document.querySelector('.workspace-tabs').hidden||!document.querySelector('.social-settings').hidden)throw Error('Developer features exposed before unlock');
                    if((await window.pywebview.api.get_social_settings()).ok)throw Error('Backend social access should be blocked');
                    if(document.getElementById('developerToggle')||!document.querySelector('.developer-settings').hidden)throw Error('Public developer entry should be removed');
                    for(let i=0;i<9;i++)document.getElementById('developerVersionTrigger').click();
                    if(document.querySelector('.developer-dialog').open)throw Error('Developer dialog opened before ten clicks');
                    document.getElementById('developerVersionTrigger').click();
                    if(!document.querySelector('.developer-dialog').open)throw Error('Tenth click did not open dialog');
                    document.getElementById('developerClose').click();
                    await new Promise(r=>setTimeout(r,50));
                    for(let i=0;i<9;i++)document.getElementById('developerVersionTrigger').click();
                    if(document.querySelector('.developer-dialog').open)throw Error('Click counter did not reset');
                    document.getElementById('developerVersionTrigger').click();
                    set('developerPassword','5830485');document.getElementById('developerSubmit').click();
                    await waitFor(()=>document.querySelector('#navList [data-page="health"]'));
                    if(document.querySelector('.usage-guide').hidden)throw Error('Developer usage guide missing');
                    if(document.querySelector('.workspace-tabs').hidden||document.querySelector('.social-settings').hidden)throw Error('Developer features missing after unlock');
                    document.querySelector('[data-page="prompts"]').click();
                    if(document.getElementById('promptProject'))throw Error('Duplicate project path row should be removed');
                    if(document.getElementById('promptVersion')||document.getElementById('promptVersions'))throw Error('Version history UI should be removed');
                    if(!document.getElementById('promptImportLocal')||!document.getElementById('promptExport').closest('.prompt-actions'))throw Error('Native import/export actions missing');
                    if(document.querySelector('.library-block')||[...document.querySelectorAll('.prompt-library h4')].some(item=>item.textContent.trim()==='範本庫'))throw Error('Prompt library should not contain nested create or library blocks');
                    if(!document.getElementById('promptGroupAdd').closest('.library-panel-heading'))throw Error('Add group should share the Prompt Library heading');
                    if(document.getElementById('promptNew')||document.getElementById('promptExportLocal'))throw Error('Old header actions should be removed');
                    if([...document.querySelectorAll('#usageTool option')].map(item=>item.value).join(',')!=='codex,claude')throw Error('Only Codex and Claude should be available');
                    if(document.getElementById('promptTags'))throw Error('Legacy free-text tags field should stay removed');
                    if(document.querySelectorAll('#promptTagOptions input').length)throw Error('Subtopics should start empty');
                    if(document.getElementById('documentType-core').disabled||!document.getElementById('documentFormArea').hidden||!document.getElementById('documentEditor').hidden)throw Error('Type must be available first');
                    if(!(document.querySelector('.document-type-tabs').compareDocumentPosition(document.getElementById('documentTopics'))&Node.DOCUMENT_POSITION_FOLLOWING)||!(document.getElementById('promptTagOptions').compareDocumentPosition(document.getElementById('promptTitle'))&Node.DOCUMENT_POSITION_FOLLOWING))throw Error('Expected type, tags, title order');
                    if(!(document.getElementById('promptCategory').compareDocumentPosition(document.getElementById('documentTopics'))&Node.DOCUMENT_POSITION_FOLLOWING)||!(document.getElementById('promptTitle').compareDocumentPosition(document.getElementById('documentAiWrite'))&Node.DOCUMENT_POSITION_FOLLOWING))throw Error('Group or writing action order incorrect');
                    const category=document.getElementById('promptCategory');
                    if(category.tagName!=='SELECT'||category.value!==''||category.options[0].value!==''||!category.closest('label').textContent.includes('若要加入提示詞範本庫請選擇'))throw Error('Prompt group should be an optional library-group selector');
                    if(!document.querySelector('.prompt-actions + .usage-guide'))throw Error('Tool guidance should be the final editor block');
                    if(!(document.getElementById('promptContent').compareDocumentPosition(document.getElementById('usageTool'))&Node.DOCUMENT_POSITION_FOLLOWING))throw Error('Prompt content should appear before tool guidance');
                    if(!document.getElementById('promptClear').closest('.prompt-actions'))throw Error('Clear action missing');
                    if(document.querySelector('.prompt-content-heading label').textContent.trim()!=='預覽提示詞')throw Error('Prompt preview label is incorrect');
                    if(document.getElementById('promptContent').tagName!=='PRE'||document.getElementById('promptContent').contentEditable==='false')throw Error('Markdown preview should stay directly editable');
                    if(!document.getElementById('promptBuild').disabled||document.getElementById('promptBuild').textContent.trim()!=='建立提示詞')throw Error('Create prompt should start disabled');
                    document.getElementById('documentType-memory').click();
                    if(document.getElementById('documentFormArea').hidden||!document.getElementById('documentFields').hidden)throw Error('Tags and title should appear before form');
                    document.querySelector('#documentTopics input[value="其他"]').click();
                    if(document.querySelectorAll('#promptTagOptions input').length)throw Error('Other should have no subtopics');
                    document.querySelector('#documentTopics input[value="撰寫企劃"]').click();
                    document.querySelector('#promptTagOptions input[value="撰寫文案"]').click();
                    document.querySelector('#promptTagOptions input[value="專案企劃"]').click();
                    if(document.querySelectorAll('#promptTagOptions input:checked').length!==1||document.querySelectorAll('#documentTopics input:checked').length!==1)throw Error('Topics must be single selection');
                    document.querySelector('#promptTagOptions input[value="撰寫文案"]').click();

                    set('promptTitle','標籤模板驗收');
                    if(document.getElementById('documentFields').hidden)throw Error('Title should reveal fields');
                    set('documentField-role','整理公司已確認背景');
                    const planningQuestion=document.getElementById('question-task').textContent;
                    document.querySelector('#documentTopics input[value="開發程式"]').click();
                    document.querySelector('#promptTagOptions input[value="寫網頁"]').click();
                    if(document.getElementById('question-task').textContent===planningQuestion||document.getElementById('documentField-role').value)throw Error('Topic questions or isolated answers incorrect');
                    set('documentField-role','網頁專用角色');
                    document.querySelector('#documentTopics input[value="撰寫企劃"]').click();
                    document.querySelector('#promptTagOptions input[value="撰寫文案"]').click();
                    if(document.getElementById('documentField-role').value!=='整理公司已確認背景')throw Error('Topic draft not restored');

                    if(document.getElementById('promptBuild').disabled)throw Error('Create prompt should enable after title input');
                    document.getElementById('promptBuild').click();
                    await waitFor(()=>document.getElementById('promptContent').value.includes('撰寫企劃/撰寫文案'));
                    if(!document.querySelector('#promptContent .md-heading-2'))throw Error('Markdown heading styling is missing');
                    if(document.getElementById('promptStructurePanel').hidden)throw Error('Generated prompt structure editor should open');
                    window.confirm=()=>true;
                    document.getElementById('promptImportLocal').click();
                    await waitFor(()=>document.getElementById('promptTitle').value==='本機匯入');
                    if(!document.getElementById('promptContent').value.includes('本機提示詞'))throw Error('Native prompt import did not fill the draft');
                    if(document.getElementById('promptBuild').textContent.trim()!=='修正提示詞'||document.getElementById('promptBuild').disabled)throw Error('Imported prompt should enable correction mode');
                    document.getElementById('promptBuild').click();
                    await waitFor(()=>!document.getElementById('promptStructurePanel').hidden);
                    if(document.getElementById('promptSectionSelect').options.length!==3)throw Error('Imported Markdown headings were not parsed into items');
                    document.getElementById('promptSectionSelect').value='1';document.getElementById('promptSectionSelect').dispatchEvent(new Event('change',{bubbles:true}));
                    set('promptSectionBody','先確認範圍與驗收方式。');document.getElementById('promptSectionApply').click();
                    await waitFor(()=>document.getElementById('promptContent').value.includes('先確認範圍與驗收方式。'));
                    if(!document.querySelector('[data-template-card="develop-feature"] [data-delete-template]'))throw Error('Personal library controls should work without a project');
                    stage='personal group create';
                    window.prompt=()=> '未選資料夾群組';window.confirm=()=>true;document.getElementById('promptGroupAdd').click();
                    await waitFor(()=>document.querySelector('[data-group-name="未選資料夾群組"]'));
                    stage='personal card drag';
                    await dragCard(document.querySelector('[data-template-card="develop-feature"]'),document.querySelector('[data-group-name="未選資料夾群組"]'),31);
                    await waitFor(()=>document.querySelector('[data-group-name="未選資料夾群組"] [data-template-card="develop-feature"]'));
                    await waitFor(()=>document.body.classList.contains('template-order-saving'));
                    await waitFor(()=>!document.body.classList.contains('template-order-saving'));
                    const movedPersonalPreference=(await window.pywebview.api.list_prompt_template_preferences('__local_prompt_library__')).data.find(item=>item.template_key==='develop-feature');
                    if(movedPersonalPreference?.category!=='未選資料夾群組')throw Error('Personal library drag did not persist');
                    stage='personal card delete';
                    document.querySelector('[data-group-name="未選資料夾群組"] [data-delete-template]').click();
                    await new Promise(r=>setTimeout(r,900));
                    const deleteCheck=(await window.pywebview.api.list_prompt_template_preferences('__local_prompt_library__')).data.find(item=>item.template_key==='develop-feature');
                    if(!deleteCheck?.hidden)throw Error(`Personal delete did not persist: ${document.getElementById('globalMessage').textContent}`);
                    await new Promise(r=>setTimeout(r,700));
                    const remainingPersonalCard=document.querySelector('[data-template-card="develop-feature"]');
                    if(remainingPersonalCard)throw Error(`Personal card remained after persisted delete; classes=${remainingPersonalCard.className}; message=${document.getElementById('globalMessage').textContent}`);
                    const personalPreference=(await window.pywebview.api.list_prompt_template_preferences('__local_prompt_library__')).data.find(item=>item.template_key==='develop-feature');
                    if(!personalPreference?.hidden)throw Error('Personal library delete did not persist without a project');
                    stage='project selection after personal library';
                    document.getElementById('chooseRootButton').click();
                    await waitFor(()=>!document.getElementById('chooseRootButton').disabled);
                    if(document.getElementById('rootPathLabel').textContent==='尚未選擇')throw Error(`Project selection failed; button=${document.getElementById('chooseRootButton').textContent}; disabled=${document.getElementById('chooseRootButton').disabled}; root=${document.getElementById('rootPathLabel').textContent}; message=${document.getElementById('globalMessage').textContent}`);
                    stage='project prompt save';
                    await waitFor(()=>document.querySelector('[data-health-file=".agents/skills/review/SKILL.md"]'));
                    if(!document.querySelector('[data-health-file=".agents/skills/review/SKILL.md"]').textContent.includes('未發現問題'))throw Error('Clean skill should remain visible in health');
                    if(!document.getElementById('projectSummary').closest('.file-list-heading'))throw Error('Scan summary should share the file-list heading');
                    if(!document.querySelector('[data-preview-file=".agents/skills/review/SKILL.md"]'))throw Error('Project should include hidden skill files');
                    const project=(await window.pywebview.api.list_projects(document.getElementById('rootPathLabel').textContent)).data[0].path;
                    set('promptTitle','桌面橋接驗收'); set('promptContent','請完成任務。\\n\\n\\n- 請保留重要限制。\\n- 請保留重要限制。\\n');
                    document.getElementById('promptSave').click();
                    await new Promise(r=>setTimeout(r,1200));
                    const saved=(await window.pywebview.api.list_prompts(project,'桌面橋接驗收','',false)).data[0];
                    if(!saved||saved.version!==1)throw Error(`Project prompt save failed; message=${document.getElementById('globalMessage').textContent}`);
                    if(document.querySelector('.prompt-cleanup'))throw Error('Standalone duplicate cleanup still exists');
                    if(document.getElementById('promptTemplatesReset'))throw Error('Built-in restore button should be removed');
                    if(document.getElementById('promptTitle').maxLength!==20)throw Error('Prompt title should be limited to 20 characters');
                    stage='project group drag and reorder';
                    window.prompt=()=> '桌面刪除驗收';window.confirm=()=>true;document.getElementById('promptGroupAdd').click();
                    await waitFor(()=>[...document.querySelectorAll('[data-group-name]')].some(group=>group.dataset.groupName==='桌面刪除驗收'));
                    let builtinCard=document.querySelector('[data-template-card="develop-feature"]');
                    if(!builtinCard?.matches('[data-drag-kind="template"]')||!builtinCard.querySelector('[data-delete-template]'))throw Error('Built-in template drag controls missing in desktop UI');
                    if(builtinCard.querySelector('small'))throw Error('Built-in template helper text should be removed');
                    if(!builtinCard.children[0].matches('.template-drag-grip')||!builtinCard.children[1].matches('.template-card')||!builtinCard.children[2].matches('.template-delete'))throw Error('Card order should be grip, title, delete');
                    const selectionStyle=getComputedStyle(builtinCard);
                    if(selectionStyle.userSelect!=='none'&&selectionStyle.webkitUserSelect!=='none')throw Error('Template card text selection should be disabled');
                    const developGroup=document.querySelector('[data-group-name="開發"]');
                    if(developGroup.querySelector('.template-group-title > strong + .template-group-count')?.textContent!=='2')throw Error('Group count should sit beside its title and include every card');
                    if(!developGroup.querySelector('header > [data-delete-group]'))throw Error('Group delete control should sit at the top-right of the group');
                    const selection=document.getSelection(),range=document.createRange();range.selectNodeContents(builtinCard.querySelector('.template-card-title'));selection.removeAllRanges();selection.addRange(range);
                    await dragCard(builtinCard,document.querySelector('[data-group-name="桌面刪除驗收"]'),41);
                    await waitFor(()=>document.querySelector('[data-group-name="桌面刪除驗收"] [data-template-card="develop-feature"]'));
                    await waitFor(()=>!document.body.classList.contains('template-order-saving'));
                    if(!selection.isCollapsed)throw Error('Dragging should clear text selection');
                    let savedCard=document.querySelector(`[data-prompt-card="${saved.id}"]`);
                    if(!savedCard?.matches('[data-drag-kind="prompt"]')||!savedCard.querySelector('[data-delete-prompt]'))throw Error('Saved prompt drag controls missing in desktop UI');
                    await dragCard(savedCard,document.querySelector('[data-group-name="桌面刪除驗收"]'),42);
                    await waitFor(()=>document.querySelector(`[data-group-name="桌面刪除驗收"] [data-prompt-card="${saved.id}"]`));
                    await waitFor(()=>!document.body.classList.contains('template-order-saving'));
                    savedCard=document.querySelector(`[data-prompt-card="${saved.id}"]`);builtinCard=document.querySelector('[data-template-card="develop-feature"]');
                    await dragCardBefore(savedCard,builtinCard,43);
                    await waitFor(()=>document.querySelector('[data-group-name="桌面刪除驗收"] [data-card-key]')?.dataset.cardKey===`prompt:${saved.id}`);
                    await waitFor(()=>!document.body.classList.contains('template-order-saving'));
                    const persistedOrder=(await window.pywebview.api.list_prompt_card_order(project)).data.filter(item=>item.group_name==='桌面刪除驗收').map(item=>item.card_key);
                    if(persistedOrder[0]!==`prompt:${saved.id}`||persistedOrder[1]!=='template:develop-feature')throw Error('Same-group card order was not persisted');
                    document.querySelector('[data-group-name="桌面刪除驗收"] [data-delete-group]').click();
                    await waitFor(()=>!document.querySelector('[data-group-name="桌面刪除驗收"]'));
                    const moved=(await window.pywebview.api.list_prompts(project,'','',false)).data.find(item=>item.id===saved.id);
                    if(moved.category!=='一般')throw Error('Deleted group did not keep prompt');
                    const builtinPreference=(await window.pywebview.api.list_prompt_template_preferences(project)).data.find(item=>item.template_key==='develop-feature');
                    if(builtinPreference.category!=='一般')throw Error('Deleted group did not keep built-in template');
                    const writingGroup=document.querySelector('[data-group-name="寫作"]');writingGroup.querySelector('[data-delete-group]').click();
                    await waitFor(()=>!document.querySelector('[data-group-name="寫作"]'));
                    if(!document.querySelector('[data-group-name="一般"] [data-template-card="readable-summary"]'))throw Error('Deleted built-in group card did not move to fallback');
                    const writingPreference=(await window.pywebview.api.list_prompt_template_preferences(project)).data.find(item=>item.template_key==='readable-summary');
                    if(writingPreference?.category!=='一般')throw Error('Deleted built-in group was not persisted');
                    builtinCard=document.querySelector('[data-template-card="develop-feature"]');builtinCard.querySelector('[data-delete-template]').click();
                    await waitFor(()=>builtinCard.classList.contains('is-deleting'));
                    await waitFor(()=>!document.querySelector('[data-template-card="develop-feature"]'));
                    document.getElementById('promptClear').click();await waitFor(()=>!document.getElementById('promptTitle').value);set('promptTitle','可刪除桌面範本');set('promptContent','測試刪除動畫。');document.getElementById('promptSave').click();
                    await waitFor(()=>[...document.querySelectorAll('.template-card-frame')].some(card=>card.textContent.includes('可刪除桌面範本')));
                    const temporary=(await window.pywebview.api.list_prompts(project,'可刪除桌面範本','',false)).data[0];
                    const temporaryCard=document.querySelector(`[data-prompt-card="${temporary.id}"]`);temporaryCard.querySelector('[data-delete-prompt]').click();
                    await waitFor(()=>temporaryCard.classList.contains('is-deleting'));
                    await waitFor(()=>!document.querySelector(`[data-prompt-card="${temporary.id}"]`));
                    if((await window.pywebview.api.list_prompts(project,'可刪除桌面範本','',false)).data.length)throw Error('Deleted prompt still exists');
                    document.querySelector(`[data-prompt-card="${saved.id}"] [data-prompt-id]`).click();await waitFor(()=>document.getElementById('promptTitle').value==='桌面橋接驗收');
                    document.getElementById('promptExport').click();
                    await waitFor(()=>document.getElementById('toast').textContent.includes('native-export.md'));
                    const request={project_path:project,relative_path:'export.md',content:document.getElementById('promptContent').value};
                    const preview=await window.pywebview.api.preview_prompt_file(request);
                    if(!preview.ok)throw Error(preview.error);
                    const apply=await window.pywebview.api.apply_prompt_file({...request,base_hash:preview.data.base_hash,expected_exists:false});
                    if(!apply.ok)throw Error(apply.error);
                    const restored=await window.pywebview.api.restore_change(apply.data.change_id);
                    if(!restored.ok)throw Error(restored.error);
                    document.querySelector('[data-page="projects"]').click();
                    document.querySelector('[data-preview-file="AGENTS.md"]').click();
                    await waitFor(()=>!document.getElementById('editFileButton').disabled);
                    document.getElementById('editFileButton').click();
                    await waitFor(()=>document.getElementById('fileEditor').open);
                    set('editorText',document.getElementById('editorText').value+'\\n## 桌面驗收\\n\\n保留原始規則。\\n');
                    document.getElementById('editorPreview').click();
                    await waitFor(()=>!document.getElementById('editorSave').disabled);
                    document.getElementById('editorSave').click();
                    await waitFor(()=>document.getElementById('editorStatus').textContent.includes('已儲存'));
                    await new Promise(r=>setTimeout(r,500));
                    document.getElementById('editorClose').click();
                    await waitFor(()=>!document.getElementById('fileEditor').open);
                    document.querySelector('[data-page="health"]').click();
                    await waitFor(()=>document.querySelector('[data-health-file="notes.md"]'));
                    document.querySelector('[data-health-file="notes.md"]').click();
                    await waitFor(()=>document.querySelector('.health-line.flagged.error'));
                    if(document.documentElement.scrollWidth>innerWidth+1)throw Error('Desktop overflow');
                    document.querySelector('[data-page="settings"]').click();
                    if(document.getElementById('sourceList')||document.getElementById('futureList'))throw Error('Removed settings sections still exist');
                    set('cloudKey','AQ.'+'a'.repeat(35));document.getElementById('cloudSave').click();
                    await waitFor(()=>document.getElementById('cloudStatus').textContent.includes('已連結'));
                    await waitFor(()=>document.getElementById('apiStatusText').textContent.includes('已連結'));
                    if(document.getElementById('cloudKey').value)throw Error('Key not cleared from form');
                    document.querySelector('[data-page="prompts"]').click();
                    window.confirm=()=>false;document.getElementById('cloudAnalyze').click();
                    await waitFor(()=>document.getElementById('cloudAnalysisStatus').textContent.includes('已取消'));
                    window.confirm=()=>true;document.getElementById('cloudAnalyze').click();
                    await waitFor(()=>document.getElementById('cloudResult').textContent.includes('任務難度'));
                    if(document.getElementById('cloudResult').querySelector('script'))throw Error('AI output must stay literal text');
                    await waitFor(()=>!document.getElementById('cloudOptimize').classList.contains('hidden'));
                    document.getElementById('cloudOptimize').click();
                    await waitFor(()=>!document.getElementById('cloudOptimization').classList.contains('hidden'));
                    if(!document.querySelector('#cloudOptimizationDiff .diff-remove')||!document.querySelector('#cloudOptimizationDiff .diff-add'))throw Error('AI optimization diff missing');
                    document.getElementById('cloudApplyOptimization').click();
                    await waitFor(()=>document.getElementById('promptContent').value.includes('使用繁體中文'));
                    if(!document.getElementById('cloudOptimization').classList.contains('hidden'))throw Error('Applied optimization result remained active');
                    document.getElementById('promptSave').click();
                    await new Promise(r=>setTimeout(r,700));
                    const optimized=(await window.pywebview.api.list_prompts(project,'桌面橋接驗收','',false)).data[0];
                    if(optimized?.version!==2)throw Error('Optimized prompt was not saved as version 2');
                    stage='draft and clear actions';
                    set('usageTool','claude');
                    document.getElementById('promptSaveDraft').click();
                    await waitFor(()=>document.getElementById('toast').textContent.includes('已儲存草稿'));
                    const draft=(await window.pywebview.api.load_prompt_draft(project)).data;
                    if(draft.tool!=='claude'||draft.content!==document.getElementById('promptContent').value)throw Error('Draft settings were not persisted');
                    window.confirm=()=>false;document.getElementById('promptClear').click();
                    if(document.getElementById('promptContent').value!==draft.content)throw Error('Cancelled clear changed content');
                    window.confirm=()=>true;document.getElementById('promptClear').click();
                    await waitFor(()=>!document.getElementById('promptContent').value);
                    await new Promise(r=>setTimeout(r,300));
                    if(document.getElementById('promptTitle').value||document.getElementById('promptCategory').value||document.querySelector('#promptTagOptions input:checked'))throw Error('Clear fields: '+JSON.stringify({title:document.getElementById('promptTitle').value,category:document.getElementById('promptCategory').value,tags:[...document.querySelectorAll('#promptTagOptions input:checked')].map(i=>i.value)}));
                    if((await window.pywebview.api.load_prompt_draft(project)).data.content!==draft.content)throw Error('Clear deleted saved draft');
                    document.querySelector(`[data-prompt-card="${saved.id}"] [data-prompt-id]`).click();
                    await waitFor(()=>document.getElementById('promptContent').value===draft.content);
                    stage='CSV and social evidence';
                    [...document.querySelectorAll('.prompt-file-actions button')].find(b=>b.textContent==='匯入 CSV').click();
                    document.getElementById('csvChoose').click();
                    await waitFor(()=>document.querySelector('[data-csv-row]'));
                    document.getElementById('csvCommit').click();
                    await waitFor(()=>document.getElementById('csvStatus').textContent.includes('新增 1 筆'));
                    const imported=(await window.pywebview.api.list_prompts(project,'整復店貼文','',false)).data;
                    if(imported.length!==1)throw Error('CSV item not persisted');
                    document.getElementById('csvKind').value='templates';document.getElementById('csvKind').dispatchEvent(new Event('change'));
                    document.getElementById('csvChoose').click();await waitFor(()=>document.querySelector('[data-csv-row]'));
                    document.getElementById('csvCommit').click();await waitFor(()=>document.getElementById('csvStatus').textContent.includes('新增 1 筆'));
                    if(!(await window.pywebview.api.get_prompt_tag_catalog()).data.some(i=>i.tag==='社群行銷'))throw Error('CSV template missing');
                    if([...document.querySelectorAll('#promptTagOptions input')].some(i=>i.value==='社群行銷'))throw Error('CSV changed fixed taxonomy');
                    document.getElementById('csvKind').closest('dialog').close();
                    document.getElementById('socialDataTab').click();
                    document.getElementById('socialPlatform').value='threads';document.getElementById('socialPlatform').dispatchEvent(new Event('change'));
                    await new Promise(r=>setTimeout(r,200));
                    document.getElementById('socialSync').click();
                    await waitFor(()=>document.querySelector('[data-snapshot]'));
                    await waitFor(()=>!document.getElementById('socialPreview').disabled);
                    document.querySelector('[data-snapshot]').click();document.getElementById('socialPreview').click();
                    await waitFor(()=>document.getElementById('marketingSend').closest('dialog').open);
                    await waitFor(()=>!document.getElementById('marketingSend').disabled);
                    document.getElementById('marketingSend').click();await waitFor(()=>!document.getElementById('marketingResult').hidden);
                    if(!document.getElementById('marketingAdvice').textContent.includes('依據'))throw Error('Missing evidence references');
                    document.getElementById('marketingApply').click();
                    await waitFor(()=>document.getElementById('promptContent').value.includes('行動呼籲'));
                    if(document.getElementById('promptEditorView').hidden)throw Error('Editor not visible after apply');
                    if(document.documentElement.scrollWidth>innerWidth+1)throw Error('New feature overflow');
                    document.querySelector('[data-page="settings"]').click();document.getElementById('cloudClear').click();
                    await waitFor(()=>document.getElementById('cloudStatus').textContent.includes('未啟用'));
                    await waitFor(()=>document.getElementById('apiStatusText').textContent.includes('未連結'));
                    if(document.getElementById('appVersion').textContent!=='V1.0')throw Error('Unexpected app version');
                    stage='developer relock';
                    document.querySelector('[data-page="health"]').click();
                    document.getElementById('developerVersionTrigger').click();
                    await waitFor(()=>!document.querySelector('#navList [data-page="health"]'));
                    if(!document.getElementById('page-prompts').classList.contains('active'))throw Error('Version click should leave locked health page');
                    if((await window.pywebview.api.get_developer_status()).data.enabled)throw Error('Version click did not lock backend');
                    if(!document.querySelector('.workspace-tabs').hidden||!document.querySelector('.social-settings').hidden||document.getElementById('healthFiles').childElementCount)throw Error('Relock did not hide and clear developer UI');
                    for(let i=0;i<9;i++)document.getElementById('developerVersionTrigger').click();
                    if(document.querySelector('.developer-dialog').open)throw Error('Exit click counted toward next unlock');
                    document.getElementById('developerVersionTrigger').click();set('developerPassword','wrong-password');document.getElementById('developerSubmit').click();
                    await waitFor(()=>document.getElementById('developerFormStatus').textContent.includes('密碼不正確'));
                    set('developerPassword','5830485');document.getElementById('developerSubmit').click();
                    await waitFor(()=>document.querySelector('#navList [data-page="health"]'));
                    document.getElementById('developerLock').click();await waitFor(()=>!document.querySelector('#navList [data-page="health"]'));
                    document.querySelector('[data-page="projects"]').click();document.getElementById('refreshProjectsButton').click();
                    await waitFor(()=>!document.getElementById('refreshProjectsButton').disabled);
                    if(document.getElementById('globalMessage').textContent||!document.querySelector('[data-preview-file="AGENTS.md"]'))throw Error('General-mode project scan failed');
                    if(document.getElementById('healthFiles').childElementCount)throw Error('General-mode project scan ran health check');
                    stage='general-mode section optimization';
                    if(!document.querySelector('.usage-guide').hidden)throw Error('Usage guide visible after lock');
                    if((await window.pywebview.api.analyze_with_ai({content:'test',consent:true})).ok)throw Error('Locked analysis allowed');
                    document.querySelector('[data-page="settings"]').click();
                    set('cloudKey','AQ.'+'a'.repeat(35));document.getElementById('cloudSave').click();
                    await waitFor(()=>document.getElementById('cloudStatus').textContent.includes('已連結'));
                    document.querySelector('[data-page="prompts"]').click();
                    document.getElementById('promptClear').click();set('promptTitle','項目優化測試');
                    document.getElementById('documentType-memory').click();
                    set('documentField-role','測試背景');set('documentField-task','保留對象內容');
                    document.getElementById('promptBuild').click();
                    await waitFor(()=>!document.getElementById('promptStructurePanel').hidden);
                    const answerOption=[...document.getElementById('promptSectionSelect').options].find(option=>option.textContent.includes('對象與使用情境'));
                    set('promptSectionSelect',answerOption.value);document.getElementById('promptSectionSelect').dispatchEvent(new Event('change'));
                    const beforeSection=document.getElementById('promptContent').value;
                    document.getElementById('sectionOptimize').click();
                    if(!document.querySelector('.section-ai-dialog:has(#sectionAiSend)').open)throw Error('Section dialog missing');
                    document.querySelector('.section-ai-dialog:has(#sectionAiSend) [value="cancel"]').click();
                    if(document.getElementById('promptContent').value!==beforeSection)throw Error('Cancel changed content');
                    await new Promise(r=>setTimeout(r,50));
                    document.getElementById('sectionOptimize').click();document.getElementById('sectionAiSend').click();
                    await waitFor(()=>!document.getElementById('sectionAiReview').hidden);
                    if(document.getElementById('promptContent').value!==beforeSection)throw Error('AI applied without review');
                    if(!document.querySelector('#sectionAiDiff .diff-add'))throw Error('Section diff missing');
                    set('promptSectionBody','編輯期間的新內容');document.getElementById('sectionAiApply').click();
                    if(!document.getElementById('sectionAiReview').hidden||document.getElementById('promptContent').value!==beforeSection)throw Error('Stale result applied');
                    document.querySelector('.section-ai-dialog:has(#sectionAiSend) [value="cancel"]').click();await new Promise(r=>setTimeout(r,50));
                    document.getElementById('sectionOptimize').click();document.getElementById('sectionAiSend').click();
                    await waitFor(()=>!document.getElementById('sectionAiReview').hidden);
                    document.getElementById('sectionAiApply').click();
                    await waitFor(()=>!document.querySelector('.section-ai-dialog:has(#sectionAiSend)').open);
                    const afterSection=document.getElementById('promptContent').value;
                    if(!afterSection.includes('以繁體中文整理重點')||afterSection.split('## 決策與進度')[1]!==beforeSection.split('## 決策與進度')[1])throw Error('Section optimization changed other sections');
                    stage='delete general group';
                    set('promptCategory','');
                    document.getElementById('promptSave').click();
                    await waitFor(()=>document.getElementById('toast').textContent.includes('已儲存至範本庫'));
                    await waitFor(()=>document.querySelector('[data-delete-group="一般"]'));
                    document.querySelector('[data-delete-group="一般"]').click();
                    await waitFor(()=>!document.querySelector('[data-group-name="一般"]'));
                    if(!document.querySelector('[data-group-name="未分類"]'))throw Error('General group did not preserve templates');
                    stage='document project wizard';
                    document.getElementById('promptClear').click();set('promptTitle','三份文件測試');
                    document.getElementById('documentType-project').click();
                    if(document.querySelectorAll('[data-field-ai]').length!==6)throw Error('Field AI buttons missing');
                    if(!document.querySelector('[data-field-ai="role"]').disabled)throw Error('Empty correction should be disabled');
                    set('documentField-role','協助我整理需求');
                    stage='correction understanding';
                    document.querySelector('[data-field-ai="role"]').click();
                    await waitFor(()=>document.querySelector('.document-ai-dialog').open);
                    if(!document.getElementById('documentAiUnderstanding').textContent.includes('整理'))throw Error('Understanding missing');
                    document.querySelectorAll('[data-ai-answer]').forEach(input=>{input.value='是，保留原有事實';input.dispatchEvent(new Event('input'));});
                    document.getElementById('documentAiCompose').click();
                    stage='correction compose';
                    await waitFor(()=>!document.getElementById('documentAiReview').hidden);
                    await waitFor(()=>document.activeElement.id==='documentAiReviewHeading'&&document.querySelector('.document-ai-dialog').scrollTop>0);
                    const applyStyle=getComputedStyle(document.getElementById('documentAiApply'));
                    if(parseFloat(applyStyle.marginTop)<8||document.getElementById('documentAiApply').getBoundingClientRect().height>38)throw Error('Apply button spacing or height incorrect');
                    if(document.getElementById('documentField-role').value!=='協助我整理需求')throw Error('Field AI applied automatically');
                    const firstAnswer=document.querySelector('[data-ai-answer]');
                    firstAnswer.value='修正：請先確認需求';firstAnswer.dispatchEvent(new Event('input'));
                    if(!document.getElementById('documentAiReview').hidden)throw Error('Changed answer retained stale result');
                    document.getElementById('documentAiCompose').click();
                    await waitFor(()=>!document.getElementById('documentAiReview').hidden);
                    set('documentField-role','使用者最新內容');
                    document.getElementById('documentAiApply').click();
                    if(document.getElementById('documentField-role').value!=='使用者最新內容'||!document.getElementById('documentAiReview').hidden)throw Error('Stale correction overwrote newer content');
                    document.querySelector('.document-ai-dialog [value="cancel"]').click();
                    document.querySelector('[data-field-ai="role"]').click();
                    await waitFor(()=>document.querySelector('.document-ai-dialog').open);
                    document.querySelectorAll('[data-ai-answer]').forEach(input=>{input.value='保留新的限制';input.dispatchEvent(new Event('input'));});
                    document.getElementById('documentAiCompose').click();
                    await waitFor(()=>!document.getElementById('documentAiReview').hidden);
                    document.getElementById('documentAiApply').click();
                    if(!document.getElementById('documentField-role').value.includes('協助整理'))throw Error('Field AI not applied');
                    document.getElementById('documentNext').click();
                    if(!document.getElementById('documentField-role'))throw Error('Memory step missing');
                    document.getElementById('documentAiWrite').click();
                    stage='writing understanding';
                    await waitFor(()=>document.querySelector('.document-ai-dialog').open);
                    if(!document.getElementById('documentAiHeading').textContent.includes('輔助撰寫'))throw Error('Wrong writing mode');
                    document.querySelectorAll('[data-ai-answer]').forEach(input=>{input.value='請保留背景，不確定的待確認';input.dispatchEvent(new Event('input'));});
                    document.getElementById('documentAiCompose').click();
                    stage='writing compose';
                    await waitFor(()=>!document.getElementById('documentAiReview').hidden);
                    if(document.getElementById('documentField-role').value)throw Error('Writing applied without confirmation');
                    document.getElementById('documentAiApply').click();
                    if(!document.getElementById('documentField-ideas').value.includes('協助整理'))throw Error('Writing did not populate all fields');
                    set('documentField-role','這是已確認的公司背景');document.getElementById('documentNext').click();
                    set('documentField-trigger','使用者要求整理需求時');set('documentField-task','先確認資料，再列出結果');
                    document.getElementById('documentNext').click();
                    if(!document.getElementById('promptContent').value.startsWith('---'))throw Error('Skill metadata missing');
                    document.querySelector('[data-stage="core"]').click();
                    if(!document.getElementById('documentField-role').value.includes('協助整理'))throw Error('Switch lost core field');
                    set('documentField-ideas','不得更動未授權的檔案');
                    document.getElementById('promptBuild').click();
                    document.getElementById('promptSaveDraft').click();
                    await waitFor(async()=>Boolean((await window.pywebview.api.load_prompt_draft(project)).data?.document_state?.mode==='project'));
                    const projectDraft=(await window.pywebview.api.load_prompt_draft(project)).data;
                    if(!projectDraft.document_state.documents.skill.content.includes('name:'))throw Error('Project draft lost skill');
                    document.getElementById('promptClear').click();
                    await waitFor(()=>document.getElementById('promptTitle').value==='');
                    document.getElementById('chooseRootButton').click();
                    await waitFor(()=>document.getElementById('documentType-project').checked);
                    if(!document.getElementById('documentField-ideas').value.includes('未授權'))throw Error('Project draft restore lost fields');
                    document.getElementById('promptExport').click();
                    await waitFor(()=>document.getElementById('toast').textContent.includes('已輸出專案'));
                    stage='popup backdrop dismissal';
                    const backdropClick=(dialog,inside=false)=>{
                      const rect=dialog.getBoundingClientRect();
                      dialog.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,clientX:inside?rect.left+10:rect.left-2,clientY:rect.top+10}));
                      dialog.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:rect.left-2,clientY:rect.top+10}));
                    };
                    for(const dialog of document.querySelectorAll('dialog')){
                      if(!dialog.open)dialog.showModal();
                      backdropClick(dialog,true);
                      if(!dialog.open)throw Error('Dragging from inside dismissed dialog');
                      backdropClick(dialog);
                      if(dialog.open)throw Error('Backdrop did not dismiss '+dialog.className);
                    }
                    window.__smokeResult={passed:true,app_version:'V1.0',document_wizard:true,field_ai_manual_apply:true,project_export:true,developer_mode:true,csv_and_social_optimization:true,native_prompt_import_export:true,static_sidebar_fallback:true,file_export_and_restore:true,editor_saved:true,health_highlight:true,cloud_settings_analysis_and_optimization:'stub transport; no live API call',personal_library_and_live_drag:true};
                  } catch(error) { window.__smokeResult={passed:false,error:`${stage}: ${String(error)}`,ai_status:document.getElementById('documentAiStatus')?.textContent,ai_message:document.getElementById('documentAiMessage')?.textContent}; }
                })();
                """)
                while True:
                    value = window.evaluate_js("window.__smokeResult || null")
                    if value:
                        result.update(value)
                        if value.get('project_export'):
                            exported = temp / '三份文件測試'
                            assert (exported / 'AGENTS.md').is_file()
                            assert (exported / 'memory' / 'CONTEXT.md').is_file()
                            assert (exported / '.agents' / 'skills' / 'project-workflow' / 'SKILL.md').is_file()
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError("Desktop workflow timed out")
                    time.sleep(.1)
            except Exception as error:
                result.update(passed=False, error=str(error))
            finally:
                window.destroy()

        webview.start(exercise, private_mode=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
