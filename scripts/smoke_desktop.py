"""Exercise the real macOS WebKit bridge with an isolated, disposable project."""
import json
import io
import tempfile
import time
from pathlib import Path

import webview

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.desktop_api import DesktopApi
from ai_memory_app.services.cloud_advisor import CloudAdvisor


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
        db = temp / "test.sqlite3"
        initialize_database(db)

        class FixtureApi(DesktopApi):
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
        # No real network or key: exercise real WebKit bridge with a stub transport.
        def fake_cloud(req, **kwargs):
            payload = json.loads(req.data)
            instruction = payload.get('systemInstruction', {}).get('parts', [{}])[0].get('text', '')
            if '提示詞優化編輯器' in instruction:
                text = '## 任務\n\n- 請保留重要限制。\n- 使用繁體中文。'
            elif '任務分析助手' in instruction:
                text = '1. 任務難度：中\n2. 預估 Token：500–800\n3. 建議修正：先確認範圍 <script>literal</script>\n4. 方案建議：先使用現有額度'
            else:
                text = 'OK'
            return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [{'text': text}]}}]}).encode())

        api._cloud_advisor._open = fake_cloud
        window = webview.create_window("Prompt Studio isolated smoke test", str(root / "web-ui" / "index.html"), js_api=api, width=1440, height=1000)
        api.attach_window(window)

        def exercise():
            try:
                deadline = time.monotonic() + 60
                while not window.evaluate_js("Boolean(document.querySelector('#promptSave'))"):
                    if time.monotonic() > deadline:
                        diagnostics = window.evaluate_js("""
                        ({
                          readyState: document.readyState,
                          location: location.href,
                          title: document.title,
                          bodyText: document.body?.innerText?.slice(0, 500) || '',
                          promptRoot: document.querySelector('#page-prompts')?.innerHTML?.slice(0, 500) || '',
                        })
                        """)
                        raise RuntimeError(f"UI did not initialize: {diagnostics}")
                    time.sleep(.1)
                window.evaluate_js("""
                (async () => {
                  const waitFor = async (condition) => { for(let i=0;i<200;i++){if(condition()) return; await new Promise(r=>setTimeout(r,50));} throw Error('Timed out waiting for UI'); };
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
                    if(document.querySelectorAll('#navList .nav-button').length!==4)throw Error('Sidebar navigation should contain four entries');
                    if(document.getElementById('promptProject'))throw Error('Duplicate project path row should be removed');
                    if(document.getElementById('promptVersion')||document.getElementById('promptVersions'))throw Error('Version history UI should be removed');
                    if(!document.getElementById('promptImportLocal')||!document.getElementById('promptExportLocal'))throw Error('Native import/export buttons should be in the editor header');
                    if(document.querySelector('.library-block')||[...document.querySelectorAll('.prompt-library h4')].some(item=>item.textContent.trim()==='範本庫'))throw Error('Prompt library should not contain nested create or library blocks');
                    if(!document.getElementById('promptGroupAdd').closest('.library-panel-heading'))throw Error('Add group should share the Prompt Library heading');
                    if(!document.getElementById('promptNew').closest('.prompt-file-actions')||document.getElementById('promptNew').textContent.trim()!=='新增草稿')throw Error('Blank draft action should be compact and live in the editor header');
                    if(document.getElementById('promptTags'))throw Error('Legacy free-text tags field should stay removed');
                    if(document.querySelectorAll('#promptTagOptions input').length<30)throw Error('Prompt tag catalog should expose many optional tags');
                    if(!document.querySelector('#promptTagOptions input[value="寫作"]')||!document.querySelector('#promptTagOptions input[value="生成文檔"]')||!document.querySelector('#promptTagOptions input[value="驗收"]')||!document.querySelector('#promptTagOptions input[value="製作"]'))throw Error('Required prompt tags are missing');
                    const category=document.getElementById('promptCategory');
                    if(category.tagName!=='SELECT'||category.value!==''||category.options[0].value!==''||!category.closest('label').textContent.includes('若要加入提示詞範本庫請選擇'))throw Error('Prompt group should be an optional library-group selector');
                    if(!document.querySelector('.prompt-actions + .usage-guide'))throw Error('Tool guidance should be the final editor block');
                    if(!(document.getElementById('promptContent').compareDocumentPosition(document.getElementById('usageTool'))&Node.DOCUMENT_POSITION_FOLLOWING))throw Error('Prompt content should appear before tool guidance');
                    if(document.getElementById('promptClear'))throw Error('Prompt clear action should be removed');
                    if(document.querySelector('.prompt-content-heading label').textContent.trim()!=='預覽提示詞')throw Error('Prompt preview label is incorrect');
                    if(document.getElementById('promptContent').tagName!=='PRE'||document.getElementById('promptContent').contentEditable==='false')throw Error('Markdown preview should stay directly editable');
                    if(!document.getElementById('promptBuild').disabled||document.getElementById('promptBuild').textContent.trim()!=='建立提示詞')throw Error('Create prompt should start disabled');
                    set('promptTitle','標籤模板驗收');
                    document.querySelector('#promptTagOptions input[value="寫作"]').click();
                    document.querySelector('#promptTagOptions input[value="生成文檔"]').click();
                    if(document.getElementById('promptBuild').disabled)throw Error('Create prompt should enable after title input');
                    document.getElementById('promptBuild').click();
                    await waitFor(()=>document.getElementById('promptContent').value.includes('使用標籤：寫作、生成文檔'));
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
                    document.getElementById('promptNew').click();set('promptTitle','可刪除桌面範本');set('promptContent','測試刪除動畫。');document.getElementById('promptSave').click();
                    await waitFor(()=>[...document.querySelectorAll('.template-card-frame')].some(card=>card.textContent.includes('可刪除桌面範本')));
                    const temporary=(await window.pywebview.api.list_prompts(project,'可刪除桌面範本','',false)).data[0];
                    const temporaryCard=document.querySelector(`[data-prompt-card="${temporary.id}"]`);temporaryCard.querySelector('[data-delete-prompt]').click();
                    await waitFor(()=>temporaryCard.classList.contains('is-deleting'));
                    await waitFor(()=>!document.querySelector(`[data-prompt-card="${temporary.id}"]`));
                    if((await window.pywebview.api.list_prompts(project,'可刪除桌面範本','',false)).data.length)throw Error('Deleted prompt still exists');
                    document.querySelector(`[data-prompt-card="${saved.id}"] [data-prompt-id]`).click();await waitFor(()=>document.getElementById('promptTitle').value==='桌面橋接驗收');
                    document.getElementById('promptExportLocal').click();
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
                    document.querySelector('[data-page="settings"]').click();document.getElementById('cloudClear').click();
                    await waitFor(()=>document.getElementById('cloudStatus').textContent.includes('未啟用'));
                    await waitFor(()=>document.getElementById('apiStatusText').textContent.includes('未連結'));
                    if(document.getElementById('appVersion').textContent!=='V1.0')throw Error('Unexpected app version');
                    window.__smokeResult={passed:true,app_version:'V1.0',version:6,native_prompt_import_export:true,static_sidebar_fallback:true,file_export_and_restore:true,editor_saved:true,health_highlight:true,cloud_settings_analysis_and_optimization:'stub transport with before/after diff and manual apply; no live API call',cloud_consent_and_clear:true,personal_library_without_project_and_live_trello_placeholder_drag:true};
                  } catch(error) { window.__smokeResult={passed:false,error:`${stage}: ${String(error)}`}; }
                })();
                """)
                while True:
                    value = window.evaluate_js("window.__smokeResult || null")
                    if value:
                        result.update(value)
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
