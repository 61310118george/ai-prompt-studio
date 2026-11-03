# AI Prompt Studio Next

- 目前版本：**V1.0**
- 支援平台：**macOS 14+（Apple Silicon）**、**Windows 11 x64**

AI Prompt Studio Next 是本機優先的提示詞與 AI 專案文件管理桌面 App。核心功能不需 API Key；只有使用者確認執行 AI 功能時，才會把提示詞及選取的參考資料送至 Gemini。

> `web-ui/` 是桌面 App 內嵌介面，沒有瀏覽器預覽模式。CSV 與本機功能可直接使用；社群登入另需部署 `oauth-service/` 授權服務，官方登入頁會在系統瀏覽器開啟。

## 直接下載使用（不需要 Git 或 Python）

1. 按本頁綠色 **Code → Local → Download ZIP**，或[直接下載完整 ZIP](https://github.com/61310118george/ai-prompt-studio/archive/refs/heads/main.zip)。
2. 完整解壓縮，先閱讀根目錄的 **先看這裡.txt**。
3. 打開 **download/**，再解壓縮符合自己系統的程式包：

| 系統 | 下載包 | 開啟方式 |
|---|---|---|
| Windows 11 x64 | `AI-Prompt-Studio-V1.0-Windows-x64.zip` | 解壓後雙擊 `AI Prompt Studio Next.exe`；新版為單一 EXE，不需 `_internal` 資料夾 |
| macOS 14+ Apple Silicon | `AI-Prompt-Studio-V1.0-macOS-Apple-Silicon.zip` | 解壓後把 `.app` 拖到「應用程式」再開啟；不適用 Intel Mac |

下載包已包含 Python 與 App 所需套件；Windows 仍需系統提供 Edge WebView2 Runtime。首次開啟可能受系統安全檢查阻擋，本版未經商業簽章／Apple 公證，請先確認來源，勿停用防護。核心本機功能不需 API Key。

更新時先儲存並完全關閉 App，再使用新解壓的完整程式包。草稿與設定保留在使用者資料目錄。原始碼仍完整保留，開發者可繼續使用下方的 Git 安裝方式。

`download/manifest.json` 記錄兩個程式包的來源 commit、SHA-256 與驗證方式。每次更新程式後，須重新建置兩個系統並一起替換下載包，不能只更新原始碼。

## 功能與使用模式

| 主題 | 主要解決的問題 |
|---|---|
| 提示詞工作台 | 管理提示詞、批次匯入 CSV、編輯 Markdown；參考公司社群貼文數據優化提示詞 |
| 專案 | 掃描本機 Markdown、依用途分類、編輯章節，並在寫入前顯示逐行差異與備份 |
| 記憶健檢（開發人員） | 找出敏感內容、重複規則、錯誤檔名、提示詞注入與待辦事項，顯示問題行但不自動修改 |
| 設定 | 管理 Gemini、社群授權服務與 Facebook／IG／Threads 公司帳號；未設定時仍可使用本機功能 |

一般模式顯示「提示詞工作台、專案、設定」。CSV、範本、草稿、Markdown 匯入／輸出、專案編輯及 Markdown 項目 AI 優化維持可用。整個「預計使用的工具／上下文負擔／方案參考／AI 分析與全文優化」區塊、記憶健檢、社群數據與社群帳號設定僅限開發人員模式；退出模式會清除全文 AI 分析結果，後端也會阻擋受限操作。

## 系統需求

### macOS

- Apple Silicon Mac，建議 macOS 14 或更新版本。
- 從原始碼執行需要 Python 3.12。

### Windows 11

- Windows 11 x64；只有從原始碼執行才需要 64 位元 Python 3.12。
- 需要 Microsoft Edge WebView2 Runtime；Windows 11 通常已內建。
- 測試版未使用程式碼簽章，第一次執行可能出現 SmartScreen 提示。

## 開發者：Git／原始碼執行（選用）

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

## Windows 舊下載版的啟動錯誤

若顯示 `Failed to resolve Python.Runtime.Loader.Initialize`，請重新下載最新版，解壓到新的資料夾並開啟單一 EXE，不要再使用指向舊 `_internal` 版本的捷徑。草稿與設定不必刪除。

Windows 下載標記可能讓 .NET 拒絕載入解壓出的組件；新版改用單一 EXE，由 PyInstaller 在啟動時解開自身相依檔。沒有修改全機安全設定，也沒有自動移除下載標記。下載標記啟動回歸測試見 `scripts/test_windows_download.ps1`；DLL 對照診斷見 `scripts/probe_windows_dll_zone.py`。參考 [Microsoft .NET 載入說明](https://learn.microsoft.com/en-us/dotnet/framework/configure-apps/file-schema/runtime/loadfromremotesources-element)及 [PyInstaller 單檔模式](https://pyinstaller.org/en/stable/operating-mode.html#how-the-one-file-program-works)。

## 基本操作

1. 在「提示詞工作台」先選最上方的「核心文件」「AI 記憶」「技能 Skill」或「專案」，再選標籤、輸入標題。標籤維持非必填；未選文件類型時隱藏標籤與標題，填入標題後展開內容表單。也可匯入 Markdown 後逐章修正。
2. 範本卡可在群組內排序或拖到其他群組；不選專案資料夾也能使用範本庫。
3. 建立或匯入提示詞後，開啟 Markdown 項目，編輯各項目內容；右上角「AI 優化」可針對目前項目修訂。Token、上下文負擔與全文分析僅在開發人員模式顯示。
4. 在「專案」授權本機資料夾，選擇 Markdown 後編輯章節，確認逐行差異再寫入。
5. 在「記憶健檢」依檔案查看風險、行號與原文片段。

專案與健檢會遞迴掃描所選位置的 `.md`、`.markdown`，包含隱藏資料夾內的 `SKILL.md`。健檢同時列出正常與有問題的檔案；未辨識為 Agent 原生指令檔不代表無法讀取。若列表空白，請核對右上角實際路徑、讀取權限及雲端檔案下載狀態；例如搬移或同步後，兩個同名資料夾可能內容不同。掃描會略過 Git、虛擬環境、相依套件、建置目錄及符號連結，避免越界與重複掃描；無法讀取的目錄會顯示警告。

提示詞編輯下方提供「儲存範本」「清除」「儲存草稿」「輸出提示詞」。儲存範本會新增或更新範本卡，未選群組時歸入「一般」。清除需確認，只重設編輯區，不刪除已存資料。每個專案（以及個人範本庫）各保存一份草稿，包含標題、標籤、群組、內容與工具選擇；重新開啟或切回專案時恢復，草稿不會出現在範本庫。輸出提示詞使用系統另存視窗，可自選 Markdown 檔案位置。預計使用工具僅提供 Codex、Claude Code。

## 文件建立

### 三種文件與專案流程

| 文件 | 解決的問題 | 表單內容 | 輸出檔名 |
|---|---|---|---|
| 核心文件 | AI 每次開始工作都需要遵守什麼？ | 角色／場景、任務／動作、想法（長期規則） | `AGENTS.md` |
| AI 記憶 | 哪些背景已確認，哪些仍未知？ | 角色／場景、任務／動作、想法（背景與偏好） | `CONTEXT.md` |
| 技能 Skill | 哪種任務可以用固定流程重複執行？ | 角色／場景、任務／動作、想法（技能流程） | `SKILL.md` |

標籤採上下兩層，皆非必填：大分類、小分類各限選一項；切換大分類會清空小分類。「其他」不設小分類。

- 開發程式：寫網頁、開發遊戲、開發 app。
- 撰寫企劃：撰寫文案、專案企劃。
- 推廣行銷：撰寫文案、分析市場、行銷顧問。
- 其他：目前不設小分類，可自行填寫文件內容。

編輯順序為「文件類型 → 群組 → 單選標籤 → 標題 → 依文件與分類顯示的需求問題 → 建立提示詞 → 編輯 Markdown」。問題分成三組：「角色／場景：你是誰、希望 AI 如何協助」「任務／動作：要做什麼、交付什麼」「想法：額外關注與限制，例如網站排名」。每欄可用 AI 修正釐清原意、整理語句；也可用 AI 輔助撰寫依分類與標題提問，核對後套用答案。舊草稿已有的欄位會保留；舊複選標籤載入時保留第一個有效小分類，重新建立預覽後再輸出。群組與標籤非必填，AI 輔助撰寫須先有標題才可點擊。


選擇文件 tab 後，下方立即顯示文件用途說明（包含專案 tab）。每題使用白話問題，必要名詞以括號補充；輸入框下方不顯示範例或 H2／H3 對照。核心文件與 AI 記憶各六題，Skill 七題；三個維度是分組，不是三個固定問題。範例不會自動寫入答案；空白章節標記 `[待確認]`。切換分類時分別保留該分類的草稿，避免沿用不相關內容。

### 文件規格與設計依據

- **核心文件**：輸出 `AGENTS.md`，章節為「專案定位、工作約定、限制與驗收」。官方定義載入位置與作用範圍，沒有固定必填 H2；這些章節是 App 的建議模板。[OpenAI 文件](https://developers.openai.com/codex/guides/agents-md)
- **AI 記憶**：輸出 `CONTEXT.md`，章節為「背景與事實、決策與進度、偏好與待確認」。這是 App 的可攜文件，需附給 AI 或由核心文件明確指向，不是通用自動記憶格式，也不冒充 Claude 的 `MEMORY.md`。[Claude Code 文件](https://code.claude.com/docs/en/memory)
- **Skill**：輸出 YAML `name`、`description` 與 Markdown，依序包含「適用範圍、輸入與資源、執行流程、輸出與驗收、邊界與例外、輸入輸出範例」。只有中繼資料及檔案結構屬規格要求，正文標題為本 App 設計。`name` 應與技能資料夾同名。[Agent Skills 規格](https://agentskills.io/specification)

提示詞設計採用明確任務、背景、格式、限制、範例與驗收條件；參考 [OpenAI](https://developers.openai.com/api/docs/guides/prompt-engineering)、[Google](https://ai.google.dev/gemini-api/docs/prompting-strategies)、[Anthropic](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview)，並閱讀使用者提供的 [Kevin Voyage 入門文章](https://kevin.voyage/post/prompt-engineering-principles/)。以下問題與例子是本專案設計，非官方強制模板。

| 分類 | 需確認的內容 | 簡短填寫範例 |
|---|---|---|
| 開發程式／寫網頁 | 訪客、頁面、框架、表單、裝置及驗收 | 原生 PHP 服務頁，含預約表單；手機可操作 |
| 開發程式／開發遊戲 | 玩家、引擎、玩法、勝負、素材及效能 | 鍵盤操作的單人闖關原型，先不做連線 |
| 開發程式／開發 app | 系統、流程、儲存、API、權限及離線 | 本機待辦，重開後資料保留，不做雲端同步 |
| 撰寫企劃／撰寫文案 | 讀者、素材、論點、語氣及篇幅 | 將會議重點整理為主管閱讀的一頁提案 |
| 撰寫企劃／專案企劃 | 問題、範圍、資源、里程碑及風險 | 改善預約流程，列工作拆解與驗收方式 |
| 推廣行銷／撰寫文案 | 受眾、平台、事實、篇幅、CTA 及宣稱 | 三則 IG 貼文，引導詢問，不寫未確認優惠 |
| 推廣行銷／分析市場 | 地區、期間、競品、來源、樣本及口徑 | 比較三家同類服務；附來源日期，缺值不當零 |
| 推廣行銷／行銷顧問 | 基準數據、渠道、預算、實驗及指標 | 設計四週有效詢問測試，不承諾營收成長 |

維護入口：`resources/document_profiles.json` 是前後端共用的題庫。每個分類各含 `core`、`memory`、`skill`；`group` 是三維度分組、`section` 對應 H2、`label` 對應 H3，`question` 是畫面與 AI 共用的白話問題，`example` 保留為題庫參考資料，不顯示於表單；`notes` 是四個 tab 下方的用途說明。問題與範例可在此調整；新增欄位時保留穩定的 `id`，並同步跑測試及重新打包。`services/document_profiles.py` 負責載入，`web-ui/document-catalog.js` 負責答案編譯。

- **AI 修正**：各內容欄位右上角的低高度按鈕，與輸入框保留間距。欄位有內容後才啟用；確認傳送該欄文字、標題與分類後，AI 先回報條列式理解及確認問題，完成分析才開啟問答視窗。回答後同時修正語序、用詞、錯字、標點及贅詞，使語句通順；保留原意、事實、限制與程式碼，已通順的內容不強行改寫。核心文件、AI 記憶、技能及專案各步驟皆適用，核對前後內容再手動套用。
- **AI 輔助撰寫**：標題下方的全寬按鈕。依標題、分類及目前文件類型分析可能需求，列出待確認的理解與問題；逐題回答後，協助填寫目前文件的表單。專案模式只處理當前步驟，不一次生成其他文件。已有內容會列在修改前區域，確認套用才會取代對應欄位。

兩者使用設定中的 Gemini，不傳送其他專案檔。問題與回答會在第二次請求中傳送；不確定可回答「待確認」。未設定 Key 仍可手動填寫、建立與輸出。取消、格式錯誤、逾時或原文變更時不套用舊結果。AI 不應補造預算、成效或背景，結果仍需人工核對；套用後須建立提示詞更新預覽，再儲存。

產生 AI 內容後，彈窗自動捲至「套用前確認」；「套用至表單」使用較低高度並與結果保留間距。App 內彈窗可點擊外側遮罩關閉，不會把點擊穿透至下方頁面；從內容區拖曳到外側不視為關閉。文件編輯器仍保留未儲存確認及寫入中保護，開發人員解鎖中也保留忙碌保護。系統選檔及原生確認視窗依作業系統行為。

選「專案」後，依序完成核心文件、AI 記憶、技能。各步驟保留各自內容，可返回修改；草稿與範本同時保存三份文件的表單、預覽及目前步驟。表單修改後需重新建立預覽，才可輸出，避免表單與檔案不同步。技能的「用途與觸發時機」及「可重複的操作步驟」必填；前者寫入 description，最多 1,024 字，識別名稱限小寫英數與連字號，不接受 Windows 保留名稱。

「輸出專案資料夾」先列出檔案清單，再選存放位置，建立新資料夾；同名時加編號，不覆蓋既有檔案：

```text
專案名稱/
├── AGENTS.md
├── memory/CONTEXT.md
└── .agents/skills/project-workflow/SKILL.md
```

核心文件附上另外兩份文件的相對路徑。這是以 Codex 為主的可攜專案結構，不代表所有 AI 工具都會自動讀取 `AGENTS.md` 或 `memory/CONTEXT.md`；其他工具請依其原生指令檔規則載入。`CONTEXT.md` 是使用者管理的背景檔，不是工具自動更新的記憶資料庫。參考：[Codex 自訂概覽](https://learn.chatgpt.com/docs/customization/overview)、[建立 Skills](https://learn.chatgpt.com/docs/build-skills)、[Agent Skills 規格](https://agentskills.io/specification)。

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

社群 Token 與授權服務連線碼使用系統金鑰圈（macOS Keychain／Windows Credential Locker），不寫入 SQLite。金鑰圈不可用時會顯示錯誤，不降級成明文檔案。Token 與資料庫路徑綁定，移動資料庫後需重新連接。

SQLite 保存匯入模板、貼文文字、數據快照及社群 AI 優化紀錄。解除社群連線只移除本機 Token；「清除歷史數據」刪除該平台本機數據及所有社群 AI 優化紀錄，不刪除平台上的貼文。若要撤銷平台權限，另到 Meta／Threads 的應用程式授權設定移除本 App。

## 專案目錄

```text
ai-prompt-studio/
├── download/                   # 一般使用者直接解壓使用的雙平台程式包與來源紀錄
├── 先看這裡.txt                  # 不使用指令的下載與開啟說明
├── .github/workflows/          # GitHub Actions 與 Windows 自動建置
├── oauth-service/              # 社群登入授權後端、獨立依賴與 Docker 建置
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
| 文件表單、階層分類與提問 | `web-ui/document-catalog.js`；擴充 `TOPICS`、`TOPIC_GUIDANCE`、`DOCUMENT_FIELDS` |
| 文件切換、專案步驟與表單暫存 | `web-ui/document-builder.js` |
| AI 理解問答、回答及修改前後確認 | `web-ui/document-ai.js`、`src/ai_memory_app/services/document_assistance.py`、`cloud_advisor.py` |
| 文件輸出、Skill YAML 驗證與安全資料夾建立 | `src/ai_memory_app/services/document_project.py` |
| Markdown 章節編輯與舊版模板 | `web-ui/prompt-builder.js`、`web-ui/data/prompt-template-catalog.csv` |
| Markdown 編輯與逐行差異 | `web-ui/file-editor.js`、`src/ai_memory_app/services/memory_compiler.py` |
| 專案掃描與檔案用途辨識 | `src/ai_memory_app/services/project_scanner.py`、`resources/agent_catalog/v1/catalog.json` |
| 記憶健檢 | `web-ui/health-panel.js`、`src/ai_memory_app/services/memory_health.py` |
| Token 與上下文負擔 | `src/ai_memory_app/services/prompt_workbench.py`、`web-ui/prompt-workspace.js` |
| Gemini 分析與優化 | `web-ui/cloud-analysis.js`、`src/ai_memory_app/services/cloud_advisor.py` |
| CSV 預覽、批次寫入與模板覆蓋 | `web-ui/csv-import.js`、`src/ai_memory_app/services/csv_import.py` |
| 社群同步、數據快照、平台指標 | `web-ui/social-workspace.js`、`src/ai_memory_app/services/social_data.py` |
| 官方登入、回呼、一次性授權結果 | `oauth-service/app.py`；只部署在後端，不包含在桌面 App |
| 開發人員功能鎖、密碼與入口 | `src/ai_memory_app/services/developer_mode.py`、`web-ui/developer-mode.js`；受限 API 由 `desktop_api.py` 檢查 |
| macOS／Windows 資料路徑 | `src/ai_memory_app/platform_paths.py` |
| 版本號 | `web-ui/version.js`，目前固定為 `V1.0` |

### 主要 Python 分層

| 位置 | 用途 |
|---|---|
| `src/ai_memory_app/data/` | SQLite schema、migration、查詢、範本與變更紀錄 |
| `src/ai_memory_app/services/` | 掃描、健檢、Diff、備份、Token 估算與 Gemini 呼叫 |
| `src/ai_memory_app/data/models.py` | 共用資料模型 |
| `src/ai_memory_app/platform_paths.py` | 統一 macOS 與 Windows 的資料目錄、資料庫與 Key 路徑 |

## 擴充提示詞標籤

一般使用者可在「提示詞工作台 → 匯入 CSV」選擇「標籤模板」，匯入結果保存於資料庫。新表單只顯示上列固定分類，不因匯入而新增標籤。要加入分類專用內容，`tag` 填完整路徑，例如 `推廣行銷/撰寫文案`；選取對應小分類並建立文件時，會附加「自訂模板補充」。舊的其他名稱仍保存在資料庫，但不會自動套用到新表單。

`web-ui/data/prompt-template-catalog.csv` 是開發者維護的內建模板。同名使用者模板優先於內建值；改動內建檔案才需要重新打包。

| 欄位 | 用途 |
|---|---|
| `tag` | 大分類／小分類完整路徑，必填且不可重複 |
| `role` | 「角色」章節內容，必填 |
| `task` | 「任務」章節內容，必填 |
| `requirements` | 執行要求，多項以 `|` 分隔 |
| `output` | 輸出格式，多項以 `|` 分隔 |
| `acceptance` | 驗收標準，多項以 `|` 分隔 |

## CSV 批次匯入

1. 在「提示詞工作台 → 提示詞編輯」右上角點「匯入 CSV」。
2. 選擇「提示詞卡片」或「標籤模板」，可先點「匯出範例 CSV」。
3. 選檔後查看來源行、內容與錯誤，勾選要匯入的資料。
4. 同名項目預設略過；需要覆蓋時勾選「更新同名項目」。
5. 點「確認匯入」。整批成功才寫入，錯誤或取消均不會產生部分資料。

提示詞 CSV 欄位：

| 欄位 | 用途 |
|---|---|
| `title` | 必填，1–20 字的卡片標題 |
| `content` | 必填，提示詞正文，可使用多行 Markdown |
| `group` | 選填，空白歸入「一般」；不存在的群組會建立 |
| `tags` | 選填，以逗號分隔的標籤 |

採 UTF-8 CSV，可包含 BOM。含逗號、換行的儲存格需以雙引號包住；Excel／Numbers 匯出 CSV 會處理此格式。每檔最多 5 MB／1,000 筆，單筆內容沿用 App 字數限制；預覽 15 分鐘後過期。

提示詞匯入目前專案範本庫，未選資料夾時匯入個人範本庫；標籤模板全 App 共用。提示詞以「群組＋標題」判斷同名，模板以 `tag` 判斷。CSV 內重複項目會標示錯誤；既有同群組有多張同名卡片時禁止批次覆蓋，避免更新錯誤卡片。

### Markdown 項目 AI 優化

若首次載入模組中斷，App 僅在編輯器尚未建立時自動重載一次；仍失敗則顯示原因與「重新載入」按鈕，不會無限重試或只留空白。手動重新載入前會確認，尚未儲存的編輯不保留；若持續失敗，請重新解壓完整安裝包，不要只移動執行檔。


在設定啟用自己的 Gemini Key 後，點擊項目內容右上角「AI 優化」，選擇改善目標，選填使用對象與必須保留的條件，確認才送出。僅傳送目前標題、標籤、項目標題、項目內容與回答，不傳送其他章節或專案路徑。畫面顯示修改前後內容與逐行差異；「套用至目前項目」只更新該項目，仍須另行儲存範本或草稿。取消、失敗或等待期間內容變更，都不會自動覆寫原文。這是輔助改寫，不保證 AI 完全正確，請人工核對。

範本庫所有群組皆可刪除，包括「一般」。刪除「一般」時，既有範本移至「未分類」；其他群組的範本移至「一般」，不刪除範本。空群組刪除後不會自動復活；未選群組再儲存範本時，仍會建立「一般」。

維護入口：`web-ui/section-optimization.js` 管理確認問題與差異介面；`prompt-workspace.js` 負責項目套用；`services/cloud_advisor.py` 的 `optimize_section` 管理送出欄位、安全檢查與編輯規則。此功能沿用既有 pywebview 與 Gemini 連線，不新增系統依賴，macOS 與 Windows 11 共用程式碼。

## 社群數據與 AI 優化

### 使用流程

1. 先解鎖開發人員模式，再完成下方授權服務部署與 Meta 設定。
2. App「設定 → 社群帳號」填入服務 HTTPS 網址與連線碼，點「儲存連線設定」。
3. 點「連接 Facebook／IG」或「連接 Threads」，在系統瀏覽器登入並同意讀取權限。
4. 回 App 選擇公司帳號，每平台連接一個帳號；清單保留 10 分鐘。
5. 在「提示詞工作台 → 社群數據」選平台，點「同步最近 30 天」。
6. 先在提示詞編輯頁準備草稿，再選 1–10 則貼文，點「依數據優化提示詞」。
7. 檢查將送往 Gemini 的內容後確認送出，查看觀察、建議、依據快照與 Diff，再套用到草稿並儲存。

數據為最近 30 天發布的最多 100 則貼文，每次同步保存一份快照。數字是同步時的累積值，不是過去 30 天新增的互動量。可依內容類型篩選及觀看次數排序；不同平台與類型不直接合併比較。

| 平台 | 第一版讀取範圍 | 權限／帳號條件 |
|---|---|---|
| Facebook | 公司粉專貼文、反應、留言、分享；嘗試讀取 `post_media_view` | 粉專管理權限；`pages_show_list`、`pages_read_engagement`、`read_insights` |
| Instagram | 專業帳號貼文、按讚、留言、觀看、觸及、收藏、分享 | 專業帳號連結粉專；另需 `instagram_basic`、`instagram_manage_insights` |
| Threads | 自己的貼文、觀看、按讚、回覆、轉發、引用、分享 | `threads_basic`、`threads_manage_insights` |

指標受 API 版本、內容類型及帳號權限影響。Facebook 的觀看指標尤其需以部署時版本實測；不支援的欄位顯示「未提供」並列出限制，絕不填成零。讀取限流或授權失效時保留舊資料，下次手動重試。

AI 使用目前選取的快照提出行銷假設，不保證曝光增加，也不把互動當成實際預約。草稿、參考貼文、AI 設定或數據更新後，舊優化結果失效。此功能不發文、不讀取私訊、不投放廣告。

### 帳號準備

- Facebook：確認是公司「粉絲專頁」而非個人動態，登入者需有讀取該粉專數據的權限。
- IG：確認為商業／創作者專業帳號，並已連結上述粉專。本版採 Facebook Login 路徑。
- Threads：準備要授權的本人帳號，依 Meta 開發者後台要求加入測試者並接受邀請。
- 在 Meta 開發者後台建立對應應用程式及登入產品，取得 Meta App ID／Secret、Threads App ID／Secret，開啟上表讀取權限。自己的帳號也需符合後台的角色與存取等級要求。
- 確認各 App 的帳號 ID。Facebook 的允許名單填 App-scoped User ID，Threads 填 API User ID，不是粉專 ID、IG ID 或使用者名稱。可在官方 API 測試工具以相同 App 的測試授權查詢 `/me?fields=id`。

參考：[Meta 官方 IG 範例與條件](https://www.postman.com/meta/instagram/folder/u4g5a2a/instagram-api-with-facebook-login)、[Threads 授權](https://www.postman.com/meta/threads/request/rqmtcws/exchange-the-code-for-a-token)、[Threads 指標](https://www.postman.com/meta/threads/request/434u2bd/get-post-insights)、[Facebook Page Insights](https://developers.facebook.com/docs/graph-api/reference/page/insights/)。本版尚未用真實公司帳號完成 Meta API 驗收，部署前需核對後台當前可用版本及權限。

### 授權服務部署

`oauth-service/` 是獨立的 Python FastAPI 服務，只處理登入與 Token 交換。App Secret 留在伺服器，貼文數據由桌面 App 直接讀取並存入本機。服務需對外 HTTPS 網址，供 Meta 登入回呼；只啟動一個實例與一個 worker。

在支援 Docker 與 HTTPS 的主機／雲端平台部署此目錄。由專案根目錄建置：

```bash
docker build -t prompt-studio-oauth ./oauth-service
```

在部署平台的環境變數管理設定以下項目，禁止將真實 Secret 寫進 Git：

| 變數 | 設定 |
|---|---|
| `PUBLIC_BASE_URL` | 服務根網址，例如 `https://auth.example.com`，不包含路徑 |
| `BROKER_KEY` | 自行產生的 32–256 字元隨機連線碼，同時填入桌面 App |
| `META_GRAPH_VERSION` | Meta 後台當前可用的 Graph API 版本，格式 `v數字.數字`，無預設值 |
| `META_APP_ID`、`META_APP_SECRET` | Facebook／IG App 的識別碼與 Secret |
| `THREADS_APP_ID`、`THREADS_APP_SECRET` | Threads App 的識別碼與 Secret |
| `ALLOWED_FACEBOOK_IDS` | 允許登入的 Facebook App-scoped User ID，多個以逗號分隔 |
| `ALLOWED_THREADS_IDS` | 允許登入的 Threads API User ID，多個以逗號分隔 |

以 Python 產生連線碼：`python -c "import secrets; print(secrets.token_urlsafe(32))"`。

容器服務監聽 `8000`，平台應提供 HTTPS 反向代理並將 `/health` 設為健康檢查。若在自己的主機執行，以下 `--env-file` 指向主機上不加入 Git 的部署設定：

```bash
docker run --detach --restart unless-stopped --name prompt-studio-oauth \
  --env-file /absolute/path/to/oauth.env \
  -p 127.0.0.1:8000:8000 prompt-studio-oauth
```

反向代理將對外 HTTPS 流量導向 `127.0.0.1:8000`，並停用含查詢參數的存取日誌，避免記錄 OAuth 回呼 code。Meta 後台需登記完全相同的回呼網址：

- Facebook Login：`https://你的服務網域/auth/callback/facebook`
- Threads：`https://你的服務網域/auth/callback/threads`

依 Meta 後台要求填寫應用程式網域、隱私政策與資料刪除說明。此服務限制在允許名單內的自用帳號；對外提供其他公司使用前需另行完成相應審核與多使用者設計。

授權暫存只放伺服器記憶體，10 分鐘到期，桌面領取後刪除。重啟服務、切換實例或領取時網路中斷，可能需要重新登入；不應設定多 worker／多實例。服務不會定期自動同步社群數據，Token 過期後由 App 提示重新授權。

### 完成部署後的真實驗收

確認三個平台都能登入、列出自己的帳號並完成同步；用平台後台核對數筆貼文數字、指標名稱與時間。測試取消登入、撤銷權限與重新連接。自動化測試採替身回應，只能驗證流程，不能替代這項平台驗收。

## 測試

2026-11-03 下載版：macOS 187 項測試、完整桌面流程、套件自檢、原生視窗及文件 tab 均通過。Windows 已通過 [GitHub Windows Runner 測試與下載後原生視窗驗證](https://github.com/61310118george/ai-prompt-studio/actions/runs/41452287116)：先重現舊版 DLL 錯誤，再確認新版單一 EXE 在保留網路下載標記時，仍可開啟原生視窗並載入文件 tab。Runner 為 Windows Server 2022，仍需在 Windows 11 實機確認最終操作體驗。

更新前請先儲存並完全結束 App。若看到 `Error -3 while decompressing data: incorrect header check`，請完全結束後重開；若仍出現，重新下載並解壓最新版。自動化 AI 測試使用替身回應，不讀取使用者金鑰，也不呼叫 Gemini。

AI 測試使用替身回應，不讀取使用者金鑰，也不呼叫 Gemini。Windows 11 桌面實機操作仍需另行驗收；一般使用者請直接下載最新版程式包。

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
