"""Exercise the real macOS WebKit bridge with an isolated, disposable project."""
import json
import tempfile
import time
from pathlib import Path

import webview

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.desktop_api import DesktopApi


def main():
    root = Path(__file__).resolve().parents[1]
    result = {}
    with tempfile.TemporaryDirectory(prefix="prompt-studio-smoke-") as folder:
        temp = Path(folder)
        project = temp / "project"
        project.mkdir()
        db = temp / "test.sqlite3"
        initialize_database(db)

        class FixtureApi(DesktopApi):
            def choose_project_root(self):
                return self.set_project_root(str(project))

        api = FixtureApi(MemoryRepository(db), backup_root=temp / "backups")
        window = webview.create_window("Prompt Studio isolated smoke test", str(root / "web-preview" / "index.html"), js_api=api, width=1440, height=1000)
        api.attach_window(window)

        def exercise():
            try:
                deadline = time.monotonic() + 30
                while not window.evaluate_js("Boolean(document.querySelector('#promptSave'))"):
                    if time.monotonic() > deadline:
                        raise RuntimeError("UI did not initialize")
                    time.sleep(.1)
                window.evaluate_js("""
                (async () => {
                  const waitFor = async (condition) => { for(let i=0;i<200;i++){if(condition()) return; await new Promise(r=>setTimeout(r,50));} throw Error('Timed out waiting for UI'); };
                  const set = (id, value) => {const input=document.getElementById(id);input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}));};
                  try {
                    document.getElementById('chooseRootButton').click();
                    await waitFor(()=>document.getElementById('promptProject').textContent.includes('目前專案'));
                    set('promptTitle','桌面橋接驗收'); set('promptContent','請完成任務。\\n\\n\\n- 請保留重要限制。\\n- 請保留重要限制。\\n');
                    document.getElementById('promptSave').click();
                    await waitFor(()=>document.getElementById('promptVersion').textContent==='v1');
                    document.getElementById('promptDeduplicate').checked=true;
                    document.getElementById('promptAnalyze').click();
                    await waitFor(()=>document.getElementById('promptMetrics').textContent.includes('o200k_base'));
                    if(document.getElementById('promptMetrics').textContent.includes('heuristic')) throw Error('Expected bundled tokenizer');
                    document.getElementById('promptUseCandidate').click();
                    document.getElementById('promptSave').click();
                    await waitFor(()=>document.getElementById('promptVersion').textContent==='v2');
                    const project=(await window.pywebview.api.list_projects(document.getElementById('rootPathLabel').textContent)).data[0].path;
                    const request={project_path:project,relative_path:'export.md',content:document.getElementById('promptContent').value};
                    const preview=await window.pywebview.api.preview_prompt_file(request);
                    if(!preview.ok)throw Error(preview.error);
                    const apply=await window.pywebview.api.apply_prompt_file({...request,base_hash:preview.data.base_hash,expected_exists:false});
                    if(!apply.ok)throw Error(apply.error);
                    const restored=await window.pywebview.api.restore_change(apply.data.change_id);
                    if(!restored.ok)throw Error(restored.error);
                    window.__smokeResult={passed:true,runtime:document.getElementById('runtimeLabel').textContent,tokenizer:'o200k_base',version:2,file_export_and_restore:true};
                  } catch(error) { window.__smokeResult={passed:false,error:String(error)}; }
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
    output = root / "docs" / "evidence" / "desktop-smoke.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
