# AI Memory Manager 2.0 需求與範圍

2026-09-25 更新：現行規格以 [SPEC.md](SPEC.md) 為準，主題為「AI 提示詞視覺化管理 App」。新增提示詞工作台、專案提示詞庫、分類搜尋、版本封存、Token 計數與情境成本分析；以下保留為 2.0 記憶管理模組的歷史需求，不代表已全面驗收。

## 核心需求

- 以專案為單位顯示 Markdown 指令與記憶檔。
- 區分一般 Markdown 與 Agent 原生檔案，不宣稱所有 `.md` 都會自動載入。
- 第一版支援 Codex、Claude Code、Gemini CLI、OpenClaw。
- Web UI 與 macOS App 使用同一套前端程式碼。
- 核心功能本機離線可用，不依賴 AI API。
- 透過結構化表單產生穩定 Markdown。
- 寫回前必須有預覽與 Diff。
- 不得刪除非 App 管理的手寫區段。
- 必須偵測檔案在預覽後的外部修改。
- 必須建立備份、歷史與復原能力。
- 所有可寫入路徑必須位於使用者選定根目錄。
- 原有 SQLite 資料保留。

## 四大區

1. 專案
2. 記憶編程
3. 記憶健檢
4. 設定

## Agent 與檔案

### Codex

- `AGENTS.md`
- `AGENTS.override.md`

### Claude Code

- `CLAUDE.md`
- `CLAUDE.local.md`
- `.claude/rules/*.md`
- 外部 Auto Memory 只提示、不跨根目錄寫入

### Gemini CLI

- `GEMINI.md`

### OpenClaw

- `AGENTS.md`
- `MEMORY.md`
- `SOUL.md`
- `USER.md`
- `IDENTITY.md`
- `TOOLS.md`
- `HEARTBEAT.md`

## 離線 compiler

- 欄位型別：單行文字、多行文字、逐行條列、bash code block。
- 必填欄位未完成時可以預覽警告，但不可套用。
- 自動統一換行、標題、條列與空欄位省略。
- HTML 特殊字元必須 escape，避免破壞 managed comments。
- 使用固定 module ID 更新既有區段。

## 安全與資料完整性

- SHA-256 optimistic concurrency。
- 同目錄暫存檔與 `os.replace`。
- 既有檔案寫回前備份。
- 新檔復原時移除該新檔。
- 若套用後又有其他修改，拒絕直接復原。
- 拒絕絕對路徑、非 `.md`、`..` 越界與外部 symlink。
- 健檢疑似 API Key、GitHub token、private key 與 password。

## 不做事項

- 不訓練模型。
- 不在 App 執行時爬取網路模板。
- 不聲稱本機規則式 compiler 具備 LLM 語意理解。
- 不直接修改 Claude Code 使用者主目錄 Auto Memory。
- 不在第一版正式寫入 GitHub Copilot、Cursor、Windsurf 專屬規則。
- 不刪除舊 SQLite 表格或舊 PySide6 UI。

## 驗收標準

- 四種 Agent catalog 可離線載入。
- 既有手寫 Markdown 在編程後仍存在。
- managed module 重複編譯只保留一份。
- 外部修改、path traversal、symlink 越界會被拒絕。
- 備份與復原可回到完全一致的原內容。
- Browser Mock 與 DesktopApi 的方法名稱及回應格式一致。
- 375px 無水平捲動，桌面版可同時查看專案、辨識結果與內容。
- 產生可雙擊的 `AI Memory Manager Next.app`。
