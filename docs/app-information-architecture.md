# AI Memory Manager 2.0 資訊架構

2026-09-25 更新：新版預設入口為「提示詞工作台」，其後為專案、記憶編程、記憶健檢、設定。工作台以左側搜尋列表、中央模板與編輯器、右側 Token／成本分析排列，窄螢幕改為單欄。資料庫儲存與 Markdown 匯出為獨立操作。最新流程與狀態詳見 [SPEC.md](SPEC.md)，下文保留為原記憶管理模組架構。

## 核心流程

```text
選擇根目錄
→ 選擇專案
→ 掃描 Markdown 與 Agent 類型
→ 選擇原生記憶檔
→ 選擇結構化模組並填寫
→ 本機編譯 Markdown
→ 預覽與檢查 Diff
→ 安全套用
→ 保留備份、歷史與復原能力
```

## 主導航

### 1. 專案

- 選擇專案根目錄。
- 顯示直接子資料夾與根目錄專案。
- 掃描所有 `.md`，保留一般 Markdown 的可見性。
- 辨識 Codex、Claude Code、Gemini CLI、OpenClaw 原生記憶檔。
- 顯示檔案用途、大小、Agent 標籤與內容預覽。

### 2. 記憶編程

左側：

- Agent
- 原生檔案與專案內路徑
- 適用的記憶模組
- 文字、條列、程式碼等結構化欄位

右側：

- 完整 Markdown 預覽
- unified diff
- 編譯警告
- 套用到檔案
- 最近變更與復原

### 3. 記憶健檢

- 建議檔案缺漏
- `AGENT.md` 等錯誤檔名
- UTF-8、空檔、偏長檔案
- 重複規則
- 疑似 API Key、token、private key、密碼
- 字元與 token 粗估
- 依 Agent 顯示有效記憶檔與載入行為

### 4. 設定

- 離線與備份行為說明
- Agent catalog 版本與查證日期
- 官方與代表性來源
- GitHub Copilot、Cursor、Windsurf 第二階段資訊

## Web／桌面共用

```text
HTML + CSS + JavaScript
       │
       ├── Browser MockApi（UI 開發與示範）
       │
       └── pywebview DesktopApi
                  │
                  ├── project scanner
                  ├── agent catalog
                  ├── Markdown compiler
                  ├── health checker
                  ├── safe file writer
                  └── SQLite repository
```

## 主要狀態

- `root`：目前授權根目錄。
- `project`：目前專案。
- `scan`：Markdown 與 Agent 辨識結果。
- `agent/file/module`：目前編程目標。
- `CompileResult`：預覽、Diff、警告與 base hash。
- `memory_file_changes`：套用、備份與復原紀錄。
