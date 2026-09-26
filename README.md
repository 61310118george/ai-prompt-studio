# AI Prompt Studio：AI 提示詞視覺化管理 App

2026-09-25 起，核心改為「依專案整理提示詞、引導式編寫、版本管理與本機 Token／輸入成本分析」。Agent 記憶編程仍為進階功能。

## 本次專題交付

- [完整企劃書](docs/專題企劃書.md)／[可編輯 Word](output/word/AI提示詞視覺化管理App_完整企劃書.docx)／[附操作介面的 PDF](output/pdf/AI提示詞視覺化管理App_完整企劃書.pdf)／[HTML](deliverables/專題企劃書.html)
- [軟體需求與技術 Spec](docs/SPEC.md)／[可編輯 Word](output/word/AI提示詞視覺化管理App_軟體需求規格書.docx)／[附介面驗收的 PDF](output/pdf/AI提示詞視覺化管理App_軟體需求規格書.pdf)／[HTML](deliverables/軟體規格書.html)
- [目前符合度與交付紀錄](docs/現況符合度與交付紀錄.md)
- [研究與 Demo 指南](docs/研究與展示指南.md)

新版工作台提供專案隔離、標題、分類、標籤、搜尋、版本、封存、四種引導情境、Markdown 匯入／匯出及復原。桌面版使用內建 o200k_base／cl100k_base，瀏覽器示範只做明示粗估。精簡僅提出格式及可選重複條列候選，不承諾語意改寫、品質提升或固定節省比例。

工程測試與合成 Token 基準已執行；真人使用者研究與模型回答品質比較尚待實施。這些結果與已實作功能的界線詳見 spec。

macOS 本機桌面 App，以專案為單位視覺化檢查 AI Agent 的 Markdown 指令與記憶，並透過結構化表單在完全離線、不消耗 AI token 的情況下產生、預覽與安全寫回內容。

## 2.0 核心功能

- Web 與 macOS App 共用同一套 HTML / CSS / JavaScript UI。
- Python + pywebview + SQLite 本機架構。
- 正式支援 Codex、Claude Code、Gemini CLI、OpenClaw（龍蝦）。
- 專案資料夾與 Markdown 地圖。
- 結構化記憶模組與規則式 Markdown compiler。
- Markdown 預覽、unified diff、managed section 合併。
- SHA-256 外部修改偵測、atomic write、時間戳備份與復原。
- 記憶健檢、有效記憶模擬、敏感資料與錯誤檔名提醒。
- 核心功能不需要 API Key。

## 執行方式

### 直接下載 macOS 測試版

已打包的測試版位於 [`deliverables/AI Prompt Studio Next.zip`](deliverables/AI%20Prompt%20Studio%20Next.zip)。解壓縮後可取得 `AI Prompt Studio Next.app`。

此版本尚未使用 Apple Developer ID 簽章及公證；第一次開啟時若 macOS 阻擋，請在 Finder 對 App 按右鍵並選擇「打開」。

### 從原始碼執行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m ai_memory_app
```

舊版 PySide6 UI 仍可作為回退啟動：

```bash
PYTHONPATH=src python run_legacy_app.py
```

## 先在瀏覽器設計與檢查 UI

```bash
python3 -m http.server 4173 --directory .
```

打開：

```text
http://127.0.0.1:4173/web-preview/
```

瀏覽器模式使用安全示範資料；桌面 App 透過相同 UI 呼叫 Python bridge 操作真實檔案。

## 測試

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

若要使用 pytest：

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src pytest -q
```

## 打包 macOS App

```bash
bash scripts/build_macos_app.sh
```

輸出：

```text
dist/AI Prompt Studio Next.app
```

Next 版是本機 MVP，尚未做 Developer ID 簽章與 notarization。打包前若缺少 tokenizer 資源會於建置階段下載；App 執行時直接讀內建資料。

重現 Token 基準與文件：

```bash
PYTHONPATH=src .venv/bin/python scripts/benchmark_prompts.py
.venv/bin/python scripts/build_project_docs.py
```

本工作副本從 `Documents/文件 - 白子敬的MacBook Pro/Codex/prompt app` 複製原始碼建立，原位置的 App 與資料未修改。開啟 App 仍沿用下方 Application Support 路徑；測試使用獨立 SQLite。

## 本機資料

SQLite：

```text
~/Library/Application Support/AI Personal Memory Manager/ai_memory_app.sqlite3
```

檔案備份：

```text
~/Library/Application Support/AI Personal Memory Manager/backups/
```

測試可使用 `AI_MEMORY_APP_DB_PATH` 指定獨立資料庫。App 不會把 API Key 寫入記憶檔或資料庫。

## 文件

- [App 介紹](docs/app-introduction.md)
- [資訊架構](docs/app-information-architecture.md)
- [需求與範圍](docs/requirements.md)
- [資料庫設計](docs/database-schema.md)
- [決策](docs/decisions.md)
- [風險](docs/risks.md)
- [下一步](docs/next-actions.md)
