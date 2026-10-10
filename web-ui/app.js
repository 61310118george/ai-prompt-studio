import { mountPromptWorkspace } from './prompt-workspace.js';
import { fileDescription } from './file-description.js';
import { mountCloudSettings } from './cloud-analysis.js';
import { APP_VERSION } from './version.js';
import { mountFileEditor, fileGroup, GROUPS } from './file-editor.js';
import { renderHealthPanel } from './health-panel.js';

const ICONS = {
  projects: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M3 6.5h6l2 2h10v10.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6.5Z"/><path d="M3 11h18"/></svg>',
  programming: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="m8 9-3 3 3 3M16 9l3 3-3 3M14 5l-4 14"/></svg>',
  health: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M12 3 4.5 6v5.5c0 4.6 3.1 7.8 7.5 9.5 4.4-1.7 7.5-4.9 7.5-9.5V6L12 3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></svg>',
};

const NAV_ITEMS = [
  { id: "prompts", label: "提示詞工作台", icon: ICONS.programming },
  { id: "projects", label: "專案", icon: ICONS.projects },
  { id: "health", label: "記憶健檢", icon: ICONS.health },
  { id: "settings", label: "設定", icon: ICONS.settings },
];

const state = {
  page: "prompts",
  runtime: "desktop",
  catalog: null,
  root: "",
  projects: [],
  project: null,
  scan: null,
  agentId: "codex",
  fileTypeId: "codex_agents",
  moduleId: "project_overview",
  compileResult: null,
  resultView: "preview",
};

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3200);
}

function showError(message = "") {
  const box = $("#globalMessage");
  box.textContent = message;
  box.classList.toggle("hidden", !message);
  if (message) box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function setApiSidebarStatus(status = {}) {
  const connection = status.connection || (status.configured ? 'error' : 'unconfigured');
  const variants = {
    connected: ['api-connected', 'API：已連結'],
    error: ['api-error', 'API：連線異常'],
    checking: ['api-checking', 'API：檢查中'],
    unverified: ['api-checking', 'API：待驗證'],
    unconfigured: ['api-unconfigured', 'API：未連結'],
  };
  const [style, label] = variants[connection] || variants.unconfigured;
  const dot = $('#apiStatusDot'), text = $('#apiStatusText');
  dot.className = `status-dot ${style}`;
  text.textContent = label;
  text.title = status.connection_message || label;
}

async function withBusy(button, label, action) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = label;
  showError();
  try { return await action(); }
  catch (error) { showError(error.message || String(error)); return null; }
  finally { button.textContent = original; button.disabled = false; }
}

function assertResponse(response) {
  if (!response?.ok) throw new Error(response?.error || "本機服務沒有回傳有效結果。");
  return response.data;
}

class AppBridge {
  constructor(api) { this.api = api; this.runtime = "desktop"; }
  static async create() {
    const desktopReady = () => typeof window.pywebview?.api?.get_agent_catalog === "function";
    if (desktopReady()) return new AppBridge(window.pywebview.api);
    await new Promise((resolve) => {
      let resolved = false;
      let timer;
      const done = () => {
        if (!resolved) {
          resolved = true;
          clearInterval(timer);
          resolve();
        }
      };
      window.addEventListener("pywebviewready", done, { once: true });
      const startedAt = Date.now();
      timer = setInterval(() => {
        if (desktopReady() || Date.now() - startedAt >= 10000) done();
      }, 50);
    });
    if (!desktopReady()) throw new Error("桌面服務尚未就緒，請重新啟動 App。");
    return new AppBridge(window.pywebview.api);
  }
  call(method, ...args) { return this.api[method](...args); }
}

let bridge;
let promptWorkspace;
let fileEditor;

function buildNavigation() {
  $("#navList").innerHTML = NAV_ITEMS.map((item) => `<button class="nav-button${item.id === state.page ? " active" : ""}" type="button" data-page="${item.id}" aria-current="${item.id === state.page ? "page" : "false"}">${item.icon}<span>${item.label}</span></button>`).join("");
  document.querySelectorAll(".nav-button").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.page)));
}

function setPage(pageId) {
  state.page = pageId;
  document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.id === `page-${pageId}`));
  document.querySelectorAll(".nav-button").forEach((button) => {
    const active = button.dataset.page === pageId;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  $("#pageTitle").textContent = NAV_ITEMS.find((item) => item.id === pageId)?.label || "AI Memory";
  $("#mainContent").focus({ preventScroll: true });
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

async function chooseRoot() {
  const result = assertResponse(await bridge.call("choose_project_root"));
  if (!result) return;
  await loadProjects(result);
}

async function loadProjects(root) {
  state.root = root;
  $("#rootPathLabel").textContent = root;
  state.projects = assertResponse(await bridge.call("list_projects", root));
  state.project = null;
  state.scan = null;
  renderProjects();
  if (state.projects.length) await selectProject(state.projects[0].path);
  $("#refreshProjectsButton").disabled = !state.projects.length;
}

function renderProjects() {
  $("#projectCount").textContent = state.projects.length;
  $("#projectList").innerHTML = state.projects.length ? state.projects.map((project) => `<button type="button" class="selection-item${state.project?.path === project.path ? " active" : ""}" data-project-path="${escapeHtml(project.path)}"><span>${escapeHtml(project.name)}</span><small>開啟</small></button>`).join("") : '<div class="empty-state">此根目錄下沒有專案資料夾。</div>';
  document.querySelectorAll("[data-project-path]").forEach((button) => button.addEventListener("click", () => selectProject(button.dataset.projectPath)));
}

async function selectProject(projectPath) {
  state.project = state.projects.find((project) => project.path === projectPath) || { name: projectPath.split("/").pop(), path: projectPath };
  state.scan = assertResponse(await bridge.call("scan_project", projectPath));
  state.compileResult = null;
  renderProjects();
  renderProjectScan();
  state.previewPath = null;
  $('#editFileButton').disabled=true;
  $('#filePreview').textContent='選擇文件查看內容。';$('#previewPath').textContent='未選擇檔案';
  selectBestProgrammingPath();
  await loadHistory();
  if (promptWorkspace) await promptWorkspace.reload(true);
  await runHealth();
}

function renderProjectScan() {
  const scan = state.scan;
  if (!scan) return;
  $("#fileCount").textContent = scan.markdown_count;
  const chips = scan.detected_agents.map((id) => state.catalog.agents.find((agent) => agent.id === id)?.name || id).map((name) => `<span class="agent-chip">${escapeHtml(name)}</span>`).join("");
  $("#projectSummary").innerHTML = `<strong>${escapeHtml(scan.name)}</strong><span>${scan.recognized_count}/${scan.markdown_count} 個檔案已辨識</span>${chips}`;
  $("#fileTableBody").innerHTML = scan.files.length ? Object.entries(GROUPS).filter(([group])=>scan.files.some((file)=>fileGroup(file)===group)).map(([group,label])=>`<tr class="file-group"><th colspan="4">${label} · ${scan.files.filter(f=>fileGroup(f)===group).length}</th></tr>`+scan.files.filter(f=>fileGroup(f)===group).map((file) => {
    const labels = file.classifications.length ? file.classifications.map((item) => `<span class="classification"><span class="recognition-chip">${escapeHtml(item.agent_name)} · ${escapeHtml(item.file_label)}</span><small>${escapeHtml(item.scope)} · ${escapeHtml(item.load_status)}</small></span>`).join("") : '<span class="recognition-chip generic">一般 Markdown</span>';
    const description=fileDescription(file);
    return `<tr><td class="file-name"><span class="file-path">${escapeHtml(file.relative_path)}</span><span class="file-description" title="${escapeHtml(description.source)}">${escapeHtml(description.text)}</span></td><td>${fileGroup(file)==='skills'?'<span class="recognition-chip">技能文件</span>':labels}</td><td>${formatBytes(file.size)}</td><td><button class="row-action" type="button" data-preview-file="${escapeHtml(file.relative_path)}">查看</button></td></tr>`;
  }).join('')).join("") : '<tr><td colspan="4" class="empty-cell">此專案沒有 Markdown。</td></tr>';
  document.querySelectorAll("[data-preview-file]").forEach((button) => button.addEventListener("click", () => previewFile(button.dataset.previewFile)));
  document.querySelectorAll("[data-program-file]").forEach((button) => button.addEventListener("click", () => programFile(button.dataset.programFile)));
}

async function previewFile(relativePath) {
  const file = assertResponse(await bridge.call("read_memory_file", state.project.path, relativePath));
  $("#previewPath").textContent = relativePath;
  $("#filePreview").textContent = file.content || "（空白檔案）";
  $("#filePreview").classList.toggle("muted", !file.content);
  state.previewPath=relativePath;$('#editFileButton').disabled=false;
}

function programFile(relativePath) {
  const file = state.scan.files.find((item) => item.relative_path === relativePath);
  const classification = file?.classifications[0];
  if (classification) {
    state.agentId = classification.agent_id;
    state.fileTypeId = classification.file_type_id;
  }
  renderAgentSelectors(false);
  $("#relativePathInput").value = relativePath;
  setPage("programming");
}

function renderAgentSelectors(resetPath = true) {
  const agentSelect = $("#agentSelect");
  const healthSelect = $("#healthAgentSelect");
  const options = state.catalog.agents.map((agent) => `<option value="${agent.id}">${escapeHtml(agent.name)}</option>`).join("");
  agentSelect.innerHTML = options;
  healthSelect.innerHTML = options;
  agentSelect.value = state.agentId;
  healthSelect.value = state.agentId;
  const agent = currentAgent();
  if (!agent.files.some((file) => file.id === state.fileTypeId)) state.fileTypeId = agent.files[0].id;
  $("#fileTypeSelect").innerHTML = agent.files.map((file) => `<option value="${file.id}">${escapeHtml(file.label)} — ${escapeHtml(file.purpose)}</option>`).join("");
  $("#fileTypeSelect").value = state.fileTypeId;
  $("#agentBehavior").textContent = agent.load_behavior + (agent.external_memory_note ? ` ${agent.external_memory_note}` : "");
  if (resetPath) selectBestProgrammingPath();
  renderModules();
}

function currentAgent() { return state.catalog.agents.find((agent) => agent.id === state.agentId); }
function currentFileType() { return currentAgent().files.find((file) => file.id === state.fileTypeId); }
function currentModule() { return state.catalog.modules.find((module) => module.id === state.moduleId); }

function selectBestProgrammingPath() {
  const fileType = currentFileType();
  const existing = state.scan?.files.find((file) => file.classifications.some((item) => item.agent_id === state.agentId && item.file_type_id === state.fileTypeId));
  $("#relativePathInput").value = existing?.relative_path || fileType?.path || "";
}

function renderModules() {
  const fileType = currentFileType();
  if (!fileType.modules.includes(state.moduleId)) state.moduleId = fileType.modules[0];
  const modules = fileType.modules.map((id) => state.catalog.modules.find((item) => item.id === id));
  $("#moduleList").innerHTML = modules.map((module) => `<button type="button" class="module-card${module.id === state.moduleId ? " active" : ""}" data-module-id="${module.id}"><strong>${escapeHtml(module.title)}</strong><span>${escapeHtml(module.description)}</span></button>`).join("");
  document.querySelectorAll("[data-module-id]").forEach((button) => button.addEventListener("click", () => { state.moduleId = button.dataset.moduleId; state.compileResult = null; renderModules(); resetCompilerOutput(); }));
  renderModuleForm();
}

function renderModuleForm() {
  const module = currentModule();
  $("#moduleForm").innerHTML = `<div><h3>${escapeHtml(module.title)}</h3><p class="field-help">${escapeHtml(module.description)}</p></div>` + module.fields.map((field) => {
    const required = field.required ? '<span class="required" aria-hidden="true">*</span><span class="sr-only">必填</span>' : "";
    const helper = field.type === "list" ? "每行一項，系統會自動轉成條列。" : field.type === "code" ? "可輸入多行命令，系統會建立 bash code block。" : "內容只做安全格式化，不會用 AI 改寫語意。";
    const control = field.type === "text" ? `<input id="field-${field.id}" data-field-id="${field.id}" type="text" autocomplete="off">` : `<textarea id="field-${field.id}" data-field-id="${field.id}" rows="${field.type === "code" ? 4 : 3}" spellcheck="false"></textarea>`;
    return `<label for="field-${field.id}">${escapeHtml(field.label)} ${required}${control}<span class="field-help">${helper}</span></label>`;
  }).join("");
}

function collectModuleValues() {
  return Object.fromEntries([...document.querySelectorAll("[data-field-id]")].map((field) => [field.dataset.fieldId, field.value]));
}

function buildCompileRequest() {
  if (!state.project) throw new Error("請先到「專案」選擇一個專案。");
  const relativePath = $("#relativePathInput").value.trim();
  if (!relativePath) throw new Error("請輸入專案內的 Markdown 路徑。");
  return { project_path: state.project.path, relative_path: relativePath, agent_id: state.agentId, file_type_id: state.fileTypeId, module_id: state.moduleId, values: collectModuleValues() };
}

async function compileCurrent() {
  const request = buildCompileRequest();
  state.compileResult = assertResponse(await bridge.call("compile_memory_module", request));
  state.resultView = "preview";
  renderCompileResult();
}

function resetCompilerOutput() {
  state.compileResult = null;
  $("#compileOutput").textContent = "# 等待產生內容";
  $("#compilerStatus").textContent = "填寫左側欄位後產生預覽。";
  $("#applyButton").disabled = true;
  $("#compileWarnings").classList.add("hidden");
}

function renderCompileResult() {
  const result = state.compileResult;
  if (!result) return resetCompilerOutput();
  const isDiff = state.resultView === "diff";
  $("#previewTab").classList.toggle("active", !isDiff);
  $("#previewTab").setAttribute("aria-selected", String(!isDiff));
  $("#diffTab").classList.toggle("active", isDiff);
  $("#diffTab").setAttribute("aria-selected", String(isDiff));
  $("#compileOutput").textContent = isDiff ? (result.diff || "沒有文字差異。") : result.compiled;
  $("#compilerStatus").textContent = `${result.relative_path} · 本機編譯完成，尚未寫入檔案`;
  const warnings = $("#compileWarnings");
  warnings.innerHTML = result.warnings.map((message) => `<div>${escapeHtml(message)}</div>`).join("");
  warnings.classList.toggle("hidden", !result.warnings.length);
  $("#applyButton").disabled = result.warnings.some((message) => message.startsWith("必填"));
}

async function applyCurrent() {
  if (!state.compileResult) throw new Error("請先產生預覽。");
  if (!window.confirm(`確定要把預覽套用到 ${state.compileResult.relative_path}？\n\nApp 會先建立備份，且只更新目前選定的 managed section。`)) return;
  const request = { ...buildCompileRequest(), base_hash: state.compileResult.base_hash };
  const result = assertResponse(await bridge.call("apply_memory_change", request));
  showToast(`已安全寫入 ${result.relative_path}`);
  await selectProject(state.project.path);
  await compileCurrent();
}

async function loadHistory() {
  if (!state.project) return;
  const history = assertResponse(await bridge.call("list_change_history", state.project.path));
  $("#historyList").innerHTML = history.length ? history.map((item) => `<div class="history-item"><div><strong>${escapeHtml(item.relative_path)}</strong><span>${escapeHtml(item.module_id)} · ${new Date(item.created_at).toLocaleString("zh-TW", { hour12: false })} · ${escapeHtml(item.status)}</span></div><button type="button" class="text-button" data-restore-id="${item.id}" ${item.status !== "applied" ? "disabled" : ""}>復原</button></div>`).join("") : '<div class="empty-state">尚無變更紀錄。</div>';
  document.querySelectorAll("[data-restore-id]").forEach((button) => button.addEventListener("click", () => restoreChange(button.dataset.restoreId)));
}

async function restoreChange(changeId) {
  if (!window.confirm("確定要復原這次變更？若檔案之後又被修改，App 會拒絕覆蓋。")) return;
  assertResponse(await bridge.call("restore_change", Number(changeId)));
  showToast("已復原檔案內容");
  await selectProject(state.project.path);
}

async function runHealth() {
  if (!state.project) throw new Error("請先到「專案」選擇一個專案。");
  const result = assertResponse(await bridge.call("run_memory_health_check", state.project.path, $("#healthAgentSelect").value));
  renderHealth(result);
}

function renderHealth(result) {
  renderHealthPanel({result,bridge,project:state.project.path,esc:escapeHtml,openEditor:path=>fileEditor.open(path)});
  return;
  /* Retired load-order layout.
  const stats = [result.summary.errors, result.summary.warnings, result.summary.info, result.summary.estimated_tokens];
  document.querySelectorAll("#healthStats strong").forEach((node, index) => { node.textContent = Number(stats[index]).toLocaleString("zh-TW"); });
  $("#loadBehavior").textContent = result.load_behavior;
  $("#effectiveFiles").innerHTML = result.effective_files.length ? result.effective_files.map((file) => `<li><code>${escapeHtml(file.relative_path)}</code><span>${escapeHtml(file.purpose)} · ${escapeHtml(file.scope)}</span></li>`).join("") : '<li class="empty-state">目前沒有偵測到會載入的專案記憶檔。</li>';
  $("#issueCount").textContent = result.issues.length;
  const severity = { error: "錯誤", warning: "警告", info: "提醒" };
  $("#issueList").innerHTML = result.issues.length ? result.issues.map((issue) => `<article class="issue-item"><span class="severity ${issue.level}">${severity[issue.level]}</span><div><strong>${escapeHtml(issue.title)}</strong><p>${escapeHtml(issue.detail)}</p>${issue.path ? `<code>${escapeHtml(issue.path)}</code>` : ""}</div></article>`).join("") : '<div class="empty-state">目前沒有發現問題。</div>';
  */
}

function renderSettings() {
  $("#catalogVersion").textContent = state.catalog.catalog_version;
  $("#catalogVerified").textContent = state.catalog.verified_at;
}

function bindEvents() {
  $("#chooseRootButton").addEventListener("click", () => withBusy($("#chooseRootButton"), "選擇中…", chooseRoot));
  $("#refreshProjectsButton").addEventListener("click", () => withBusy($("#refreshProjectsButton"), "掃描中…", () => selectProject(state.project.path)));
  $("#agentSelect").addEventListener("change", () => { state.agentId = $("#agentSelect").value; renderAgentSelectors(); });
  $("#fileTypeSelect").addEventListener("change", () => { state.fileTypeId = $("#fileTypeSelect").value; state.compileResult = null; selectBestProgrammingPath(); renderModules(); resetCompilerOutput(); });
  $("#clearFormButton").addEventListener("click", () => { $("#moduleForm").reset(); resetCompilerOutput(); });
  $("#compileButton").addEventListener("click", () => withBusy($("#compileButton"), "編譯中…", compileCurrent));
  $("#applyButton").addEventListener("click", () => withBusy($("#applyButton"), "寫入中…", applyCurrent));
  $("#previewTab").addEventListener("click", () => { state.resultView = "preview"; renderCompileResult(); });
  $("#diffTab").addEventListener("click", () => { state.resultView = "diff"; renderCompileResult(); });
  $("#refreshHistoryButton").addEventListener("click", loadHistory);
  $("#runHealthButton").addEventListener("click", () => withBusy($("#runHealthButton"), "檢查中…", runHealth));
}

async function init() {
  buildNavigation();
  bridge = await AppBridge.create();
  state.runtime = bridge.runtime;
  $('#appVersion').textContent = APP_VERSION;
  setApiSidebarStatus({connection:'unconfigured', connection_message:'尚未設定 API Key。'});
  document.addEventListener('cloud-status-changed', event => setApiSidebarStatus(event.detail));
  state.catalog = assertResponse(await bridge.call("get_agent_catalog"));
  renderAgentSelectors();
  renderSettings();
  bindEvents();
  const historyPanel=$('.history-section');historyPanel.classList.add('panel');$('#page-projects').append(historyPanel);
  promptWorkspace = mountPromptWorkspace({bridge, state, escapeHtml, reportError: showError, toast: showToast});
  mountCloudSettings(bridge);
  fileEditor=mountFileEditor({bridge,state,esc:escapeHtml,toast:showToast,toWorkbench:async draft=>{if(!await promptWorkspace.importDraft(draft))return false;setPage('prompts');return true;},refreshed:async path=>{state.scan=assertResponse(await bridge.call('scan_project',state.project.path));renderProjectScan();await previewFile(path);await loadHistory();await runHealth();await promptWorkspace.reload();}});
  $('#editFileButton').onclick=()=>fileEditor.open(state.previewPath).catch(e=>showError(e.message));
  setPage(state.page);
}

init().catch((error) => showError(`初始化失敗：${error.message || error}`));
