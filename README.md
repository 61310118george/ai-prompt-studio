# AI Prompt Studio Next

- 目前版本：**V1.0**
- 支援平台：**macOS 14+（Apple Silicon）**、**Windows 11 x64**

AI Prompt Studio Next 是本機優先的提示詞與 AI 專案文件管理工具。核心功能不需 API Key；只有使用者主動執行 AI 輔助功能時，才會把目前編輯的內容送至 Gemini。

## 直接下載使用（不需要 Git 或 Python）

1. 按本頁綠色 **Code → Local → Download ZIP**，或[直接下載完整 ZIP](https://github.com/61310118george/ai-prompt-studio/archive/refs/heads/main.zip)。
2. 完整解壓縮，先閱讀根目錄的 **START-HERE.txt**。
3. 打開 **download/**，再解壓縮符合自己系統的程式包。

| 系統 | 下載包 | 開啟方式 |
|---|---|---|
| Windows 11 x64 | `AI-Prompt-Studio-V1.0-Windows-x64.zip` | 解壓後雙擊 `AI Prompt Studio Next.exe` |
| macOS 14+ Apple Silicon | `AI-Prompt-Studio-V1.0-macOS-Apple-Silicon.zip` | 解壓後把 `.app` 拖到「應用程式」再開啟 |

下載包已包含 Python 與 App 所需套件；Windows 仍需系統提供 Edge WebView2 Runtime。首次開啟可能受系統安全檢查阻擋，本版未經商業簽章或 Apple 公證，請先確認下載來源，勿停用系統防護。

更新時請先儲存並完全關閉 App，再使用新解壓的完整程式包。草稿與設定保留在使用者資料目錄。`download/manifest.json` 記錄雙平台程式包的來源 commit、SHA-256 與驗證方式。

## 主要功能

| 主題 | 解決的問題 |
|---|---|
| 提示詞工作台 | 建立、整理、匯入、輸出提示詞，以及產生核心文件、AI 記憶與 Skill |
| 專案 | 掃描本機 Markdown、依用途分類、編輯章節，並在寫入前確認逐行差異 |
| 設定 | 管理 Gemini Key、模型與連線測試；未設定時仍可使用本機功能 |

`web-ui/` 是桌面 App 內嵌介面，不提供獨立瀏覽器預覽模式。

## 系統需求

### macOS

- Apple Silicon Mac，建議 macOS 14 或更新版本。
- 從原始碼執行需要 Python 3.12。

### Windows 11

- Windows 11 x64；只有從原始碼執行才需要 64 位元 Python 3.12。
- 需要 Microsoft Edge WebView2 Runtime；Windows 11 通常已內建。
- 測試版未使用程式碼簽章，第一次執行可能出現 SmartScreen 提示。

## Git／原始碼執行（選用）

### macOS

```bash
git clone https://github.com/61310118george/ai-prompt-studio.git
cd ai-prompt-studio
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
PYTHONPATH=src python run_app.py
```

### Windows 11

在 PowerShell 執行：

```powershell
git clone https://github.com/61310118george/ai-prompt-studio.git
Set-Location ai-prompt-studio
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe run_app.py
```

## Windows 舊下載版啟動錯誤

若顯示 `Failed to resolve Python.Runtime.Loader.Initialize`，請重新下載最新版，解壓到新的資料夾後開啟單一 EXE，不要再使用指向舊 `_internal` 版本的捷徑。草稿與設定不必刪除。

新版改用 PyInstaller 單檔模式，避免 Windows 下載標記造成 .NET 組件載入失敗。下載標記回歸測試位於 `scripts/test_windows_download.ps1`；DLL 診斷工具位於 `scripts/probe_windows_dll_zone.py`。

## 基本操作

1. 在「提示詞工作台」選擇「核心文件」「AI 記憶」「技能 Skill」或「專案」。
2. 選填群組與標籤，輸入標題後完成對應表單；也可匯入 Markdown 後逐章修正。
3. 使用「AI 輔助撰寫」整理需求，或用欄位右上角的「AI 修正」核對理解並改善語句。
4. 建立預覽後，可儲存範本、儲存草稿或輸出 Markdown／專案資料夾。
5. 在「專案」授權本機資料夾，選擇 Markdown、編輯章節，確認逐行差異後再寫入。

範本卡可在群組內排序或拖到其他群組；不選專案資料夾也能使用範本庫。所有群組皆可刪除，包括「一般」；刪除群組只會移動其中的範本，不會一併刪除範本內容。

專案會遞迴掃描所選位置的 `.md`、`.markdown`，包含隱藏資料夾內的 `SKILL.md`。掃描會略過 Git、虛擬環境、相依套件、建置目錄及符號連結；若列表空白，請核對右上角實際路徑、讀取權限及雲端檔案下載狀態。

## 文件建立

| 文件 | 用途 | 主要內容 | 輸出檔名 |
|---|---|---|---|
| 核心文件 | 記錄 AI 每次工作都要遵守的規則 | 專案定位、工作約定、限制與驗收 | `AGENTS.md` |
| AI 記憶 | 保存已確認背景、決策與待確認事項 | 背景與事實、決策與進度、偏好與待確認 | `CONTEXT.md` |
| 技能 Skill | 把固定任務整理成可重複流程 | 適用範圍、輸入、步驟、輸出與例外 | `SKILL.md` |
| 專案 | 一次完成上述三種文件 | 核心文件 → AI 記憶 → Skill | 專案資料夾 |

標籤分成大分類與小分類，皆為單選且非必填：

- 開發程式：寫網頁、開發遊戲、開發 app。
- 撰寫企劃：撰寫文案、專案企劃。
- 推廣行銷：撰寫文案、分析市場、行銷顧問。
- 其他：不設小分類，可自行填寫內容。

每個文件會依文件類型與標籤顯示不同問題，協助確認使用者、任務、限制、輸出與驗收方式。問題以白話呈現，空白章節以 `[待確認]` 標記，不會把範例自動寫入答案。

### 文件規格

- **核心文件**：輸出 `AGENTS.md`。App 提供建議章節，但不把建議模板冒充成官方固定格式。[OpenAI 文件](https://developers.openai.com/codex/guides/agents-md)
- **AI 記憶**：輸出 `CONTEXT.md`。這是可攜背景檔，需主動提供給 AI 或由核心文件指向，不是所有工具都會自動讀取的通用記憶格式。[Claude Code 文件](https://code.claude.com/docs/en/memory)
- **Skill**：輸出 YAML `name`、`description` 與 Markdown 正文；`name` 應與技能資料夾同名。[Agent Skills 規格](https://agentskills.io/specification)

題庫維護入口為 `resources/document_profiles.json`。`group` 控制畫面分組、`section` 對應 H2、`label` 對應 H3、`question` 是表單問題、`example` 只作題庫參考。載入邏輯位於 `src/ai_memory_app/services/document_profiles.py`，答案編譯位於 `web-ui/document-catalog.js`。

### AI 輔助撰寫與 AI 修正

- **AI 輔助撰寫**：依標題、分類與文件類型提出問題，回答後先顯示修改前後內容，確認才套用至表單。
- **AI 修正**：分析目前欄位與標題是否表達一致，再修正語序、用詞、錯字、標點及贅詞；保留原意、事實、限制與程式碼。

兩者只傳送目前編輯所需的文字，不傳送其他專案檔或路徑。未設定 Gemini Key 仍可手動填寫與輸出。取消、逾時、格式錯誤或原文已變更時，不會套用舊結果；AI 結果仍須人工核對。

### 專案資料夾輸出

選擇「專案」後，依序完成核心文件、AI 記憶與 Skill。輸出前會列出檔案清單，再讓使用者選擇位置；同名資料夾會自動加編號，不覆蓋既有檔案。

```text
專案名稱/
├── AGENTS.md
├── memory/CONTEXT.md
└── .agents/skills/project-workflow/SKILL.md
```

## 資料位置與隱私

| 平台 | SQLite、API Key 與備份預設位置 |
|---|---|
| macOS | `~/Library/Application Support/AI Prompt Studio/` |
| Windows 11 | `%LOCALAPPDATA%\AI Prompt Studio\` |

可用環境變數調整資料位置：

- `AI_PROMPT_STUDIO_DATA_DIR`：改變整個本機資料目錄。
- `AI_PROMPT_STUDIO_DB_PATH`：只改變 SQLite 檔案位置。
- `AI_MEMORY_APP_DB_PATH`：舊版相容用的 SQLite 覆寫名稱。

Gemini Key 不會寫入專案 Markdown 或 App 安裝目錄，但目前仍保存在本機資料目錄，不是作業系統金鑰圈。共用電腦請使用獨立的作業系統帳號。

## 專案目錄

```text
ai-prompt-studio/
├── download/                   # 可直接解壓使用的雙平台程式包與來源紀錄
├── START-HERE.txt              # 不使用指令的繁體中文開啟說明
├── .github/workflows/          # GitHub Actions 與 Windows 自動建置
├── resources/                  # 文件題庫、規格與離線資料
├── scripts/                    # 雙平台打包、資料準備與桌面 smoke test
├── src/ai_memory_app/          # Python 桌面層、資料層與本機服務
├── tests/                      # Python 自動化測試
├── web-ui/                     # 桌面 App 內嵌 HTML／CSS／JavaScript 介面
├── run_app.py                  # 正式桌面 App 入口
├── requirements.txt            # 執行期套件
├── requirements-dev.txt        # 測試與打包套件
└── pytest.ini                  # 測試設定
```

`build/`、`dist/`、`release/`、虛擬環境與快取是本機產物，已由 Git 忽略，不屬於專案原始碼。

## 常用調整位置

| 要調整的內容 | 位置 |
|---|---|
| App 啟動、視窗與 Python/JavaScript bridge | `src/ai_memory_app/app.py`、`src/ai_memory_app/services/desktop_api.py` |
| 範本群組、拖曳、刪除與匯入輸出 | `web-ui/prompt-workspace.js`、`src/ai_memory_app/data/prompt_library.py` |
| 文件題庫、表單與階層分類 | `resources/document_profiles.json`、`web-ui/document-catalog.js` |
| 文件切換、專案步驟與暫存 | `web-ui/document-builder.js` |
| AI 問答、修改前後確認 | `web-ui/document-ai.js`、`src/ai_memory_app/services/document_assistance.py` |
| 文件輸出與 Skill YAML 驗證 | `src/ai_memory_app/services/document_project.py` |
| Markdown 章節編輯與逐行差異 | `web-ui/file-editor.js`、`src/ai_memory_app/services/memory_compiler.py` |
| 專案掃描與檔案用途辨識 | `src/ai_memory_app/services/project_scanner.py`、`resources/agent_catalog/v1/catalog.json` |
| CSV 預覽與批次寫入 | `web-ui/csv-import.js`、`src/ai_memory_app/services/csv_import.py` |
| Markdown 項目 AI 優化 | `web-ui/section-optimization.js`、`src/ai_memory_app/services/cloud_advisor.py` |
| macOS／Windows 資料路徑 | `src/ai_memory_app/platform_paths.py` |
| 版本號 | `web-ui/version.js` |

Python 分層：`src/ai_memory_app/data/` 管理 SQLite、migration、查詢與範本；`src/ai_memory_app/services/` 管理掃描、Diff、備份、文件與 AI 服務；`platform_paths.py` 統一 macOS 與 Windows 的資料路徑。

## CSV 批次匯入

1. 在「提示詞工作台 → 提示詞編輯」右上角點「匯入 CSV」。
2. 選擇「提示詞卡片」或「標籤模板」，可先匯出範例 CSV。
3. 查看來源行、內容與錯誤，勾選要匯入的資料。
4. 同名項目預設略過；需要覆蓋時勾選「更新同名項目」。
5. 點「確認匯入」。整批成功才寫入，錯誤或取消不會產生部分資料。

提示詞 CSV 欄位：

| 欄位 | 用途 |
|---|---|
| `title` | 必填，1–20 字的卡片標題 |
| `content` | 必填，可使用多行 Markdown |
| `group` | 選填，空白歸入「一般」 |
| `tags` | 選填，以逗號分隔 |

採 UTF-8 CSV，可包含 BOM；每檔最多 5 MB／1,000 筆。提示詞匯入目前專案範本庫，未選資料夾時匯入個人範本庫；標籤模板全 App 共用。

## Markdown 項目 AI 優化

設定 Gemini Key 後，可點擊項目右上角「AI 優化」，選擇改善目標，並選填使用對象與必須保留的條件。畫面會顯示修改前後內容與逐行差異；套用只更新目前項目，仍須另行儲存範本或草稿。

若首次載入模組中斷，App 只會自動重載一次；仍失敗時會顯示原因與「重新載入」按鈕。若持續失敗，請重新解壓完整安裝包，不要只移動執行檔。

## 測試

macOS：

```bash
python -m pip install -r requirements-dev.txt
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python run_app.py --self-test
python -m compileall -q src tests scripts
```

Windows PowerShell：

```powershell
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH = "src"
python -m pytest -q
python run_app.py --self-test
python -m compileall -q src tests scripts
```

Windows 下載包由 GitHub Windows Runner 建置與執行原生視窗 smoke test。Runner 使用 Windows Server 2022；Windows 11 的最終操作體驗仍需實機確認。自動化 AI 測試使用替身回應，不讀取使用者 Key，也不呼叫 Gemini。
