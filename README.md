# AI Prompt Studio Next

- 目前版本：**V1.0**
- 支援平台：**macOS 14+（Apple Silicon）**、**Windows 11 x64**

AI Prompt Studio Next 是本機優先的提示詞與 AI 專案文件管理桌面 App。核心功能不需 API Key；只有使用者主動執行「AI 分析」或「AI 優化」時，才會把目前提示詞送至 Gemini。

> 本專案只提供桌面 App。`web-ui/` 是 App 內嵌介面來源，不是瀏覽器預覽網站，也不需另外啟動 Web Server。

## 四大功能

| 主題 | 主要解決的問題 |
|---|---|
| 提示詞工作台 | 建立、分組、拖曳與重用提示詞；匯入／匯出 Markdown；估算 Token；選用 AI 分析與優化 |
| 專案 | 掃描本機 Markdown、依用途分類、編輯章節，並在寫入前顯示逐行差異與備份 |
| 記憶健檢 | 找出敏感內容、重複規則、錯誤檔名、提示詞注入與待辦事項，顯示問題行但不自動修改 |
| 設定 | 管理 Gemini API Key、模型與連線測試；未設定時仍可使用所有本機功能 |

## 系統需求

### macOS

- Apple Silicon Mac，建議 macOS 14 或更新版本。
- 從原始碼執行需要 Python 3.12。
- 打包 `.app` 需要 Xcode Command Line Tools 的 `codesign`。

### Windows 11

- Windows 11 x64 與 64 位元 Python 3.12。
- 需要 Microsoft Edge WebView2 Runtime；Windows 11 通常已內建。
- 測試版未使用程式碼簽章，第一次執行可能出現 SmartScreen 提示。

PyInstaller 無法跨作業系統打包，因此 macOS 版必須在 macOS 建置，Windows 版必須在 Windows 建置。可參考 [PyInstaller 官方文件](https://pyinstaller.org/en/latest/) 與 [pywebview Windows 安裝說明](https://pywebview.flowrl.com/guide/installation)。

## 從原始碼執行

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
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
python run_app.py
```

若無法啟用 PowerShell 腳本，可直接使用虛擬環境中的 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe run_app.py
```

## 打包桌面版

### macOS

```bash
bash scripts/build_macos_app.sh
```

輸出：

- `dist/AI Prompt Studio Next.app`
- `release/AI Prompt Studio Next V1.0 macOS Apple Silicon.zip`

### Windows 11

在 PowerShell 執行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build_windows_app.ps1
```

輸出：

- `dist\AI Prompt Studio Next\AI Prompt Studio Next.exe`
- `release\AI Prompt Studio Next V1.0 Windows x64.zip`

Windows 腳本會建立 `.venv-windows`、安裝相依套件、執行 `--self-test`，再產生可完整解壓執行的 ZIP。GitHub Actions 也可在 Windows Runner 上驗證並產生 artifact。

## 基本操作

1. 在「提示詞工作台」輸入標題，可選標籤產生基本模板，或匯入 Markdown 後逐章修正。
2. 範本卡可在群組內排序或拖到其他群組；不選專案資料夾也能使用範本庫。
3. 編輯器會即時估算 Token 與上下文負擔；設定 Gemini 後可執行 AI 分析或優化。
4. 在「專案」授權本機資料夾，選擇 Markdown 後編輯章節，確認逐行差異再寫入。
5. 在「記憶健檢」依檔案查看風險、行號與原文片段。

## 資料位置與隱私

| 平台 | SQLite、API Key 與備份預設位置 |
|---|---|
| macOS | `~/Library/Application Support/AI Prompt Studio/` |
| Windows 11 | `%LOCALAPPDATA%\AI Prompt Studio\` |

可用環境變數調整位置：

- `AI_PROMPT_STUDIO_DATA_DIR`：改變整個本機資料目錄。
- `AI_PROMPT_STUDIO_DB_PATH`：只改變 SQLite 檔案位置。
- `AI_MEMORY_APP_DB_PATH`：舊版相容用的 SQLite 覆寫名稱。

Gemini Key 不會寫入專案 Markdown 或 App 安裝目錄，但目前仍是本機檔案，不是作業系統金鑰圈。共用電腦請使用獨立的作業系統帳號。

## 專案目錄

```text
ai-prompt-studio/
├── .github/workflows/          # GitHub Actions 與 Windows 自動建置
├── resources/                  # Agent 規格與離線 tokenizer 資料
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

## 專案資料夾說明

| 內容 | 位置 |
|---|---|
| App 啟動、視窗與 Python/JavaScript bridge | `src/ai_memory_app/app.py`、`src/ai_memory_app/services/desktop_api.py` |
| 範本群組、拖曳、刪除與匯入匯出 | `web-ui/prompt-workspace.js`、`src/ai_memory_app/data/prompt_library.py` |
| 標籤與提示詞模板 | `web-ui/prompt-builder.js`、`web-ui/data/prompt-template-catalog.csv` |
| Markdown 編輯與逐行差異 | `web-ui/file-editor.js`、`src/ai_memory_app/services/memory_compiler.py` |
| 專案掃描與檔案用途辨識 | `src/ai_memory_app/services/project_scanner.py`、`resources/agent_catalog/v1/catalog.json` |
| 記憶健檢 | `web-ui/health-panel.js`、`src/ai_memory_app/services/memory_health.py` |
| Token 與上下文負擔 | `src/ai_memory_app/services/prompt_workbench.py`、`web-ui/prompt-workspace.js` |
| Gemini 分析與優化 | `web-ui/cloud-analysis.js`、`src/ai_memory_app/services/cloud_advisor.py` |
| macOS／Windows 資料路徑 | `src/ai_memory_app/platform_paths.py` |
| 版本號 | `web-ui/version.js`，目前固定為 `V1.0` |

### 主要 Python 分層

| 位置 | 用途 |
|---|---|
| `src/ai_memory_app/data/` | SQLite schema、migration、查詢、範本與變更紀錄 |
| `src/ai_memory_app/services/` | 掃描、健檢、Diff、備份、Token 估算與 Gemini 呼叫 |
| `src/ai_memory_app/domain/` | 共用資料模型與領域規則 |
| `src/ai_memory_app/platform_paths.py` | 統一 macOS 與 Windows 的資料目錄、資料庫與 Key 路徑 |

## 擴充提示詞標籤

標籤模板位於 `web-ui/data/prompt-template-catalog.csv`，可用 Excel、Numbers 或文字編輯器修改，並以 UTF-8 CSV 儲存。

| 欄位 | 用途 |
|---|---|
| `tag` | 畫面顯示名稱，必填且不可重複 |
| `role` | 「角色」章節內容 |
| `task` | 「任務」章節內容 |
| `requirements` | 執行要求，多項以 `|` 分隔 |
| `output` | 輸出格式，多項以 `|` 分隔 |
| `acceptance` | 驗收標準，多項以 `|` 分隔 |

修改 CSV 後重新啟動原始碼版即可測試；正式 App 必須重新打包才會包含新資料。

## 測試

macOS：

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python run_app.py --self-test
python -m compileall -q src tests scripts
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python run_app.py --self-test
python -m compileall -q src tests scripts
```