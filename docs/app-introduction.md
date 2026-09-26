# AI Memory Manager 2.0 介紹

2026-09-25 更新：產品暫名 AI Prompt Studio，專題主題為「AI 提示詞視覺化管理 App」。新版以提示詞編寫、專案分類、版本重用與輸入成本分析為主，原 Agent 記憶工具成為進階功能。本機精簡是可追蹤規則，不宣稱自動理解任意語意；Token 減少与品質改善需要分別驗證。完整介紹與研究目的見 [專題企劃書](專題企劃書.md)。

## 產品問題

AI Agent 不會自動理解所有專案 Markdown。不同工具會讀取不同檔名、路徑與作用域，使用者通常難以回答：

- 這個專案有哪些 AI 記憶？
- 哪些檔案真的會被 Agent 載入？
- `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`MEMORY.md` 分別應該寫什麼？
- 修改後是否刪掉原本重要內容？
- 記憶是否過長、重複、衝突或包含機密？

AI Memory Manager 2.0 將這些檔案轉成可視化、可編程、可檢查與可復原的本機工作流程。

## 正式支援範圍

- Codex：`AGENTS.md`、`AGENTS.override.md`
- Claude Code：`CLAUDE.md`、`.claude/rules/*.md`
- Gemini CLI：`GEMINI.md`
- OpenClaw：`AGENTS.md`、`MEMORY.md`、`SOUL.md`、`USER.md`、`IDENTITY.md`、`TOOLS.md`、`HEARTBEAT.md`

Claude Auto Memory 位於使用者主目錄，並不是專案可攜式檔案；第一版只說明位置，不跨越已選專案根目錄寫入。

## 離線記憶編程

App 不假裝在沒有模型時能理解任意自然語言。使用者會選擇一個通用模組，例如：

- 專案目標與用途
- 技術架構與目錄地圖
- 安裝、執行與驗證指令
- 程式與文件規範
- AI 協作方式
- 修改範圍與禁止事項
- 驗證方式與完成標準
- 長期事實、偏好與決策
- 人格、使用者、工具、heartbeat

表單內容由規則式 compiler 轉成標題、條列與 code block。過程不呼叫 API、不需要 API Key，也不產生 AI token 成本。

## 安全修改

1. 讀取目前檔案並計算 SHA-256。
2. 只新增或更新 App 管理的 HTML comment 區段。
3. 顯示完整預覽與 unified diff。
4. 套用時重新比對 hash，拒絕覆蓋外部新修改。
5. 既有檔案先備份到 Application Support。
6. 使用同目錄暫存檔與 atomic replace。
7. 記錄變更並提供復原。

## 技術架構

```text
作業系統：macOS
主要語言：Python 3.12
桌面殼：pywebview + macOS WebKit
正式 UI：HTML / CSS / JavaScript ES modules
資料庫：SQLite
打包：PyInstaller
```

舊 PySide6 UI 仍保留為回退入口，但不再是 2.0 的主要畫面。

## Demo 建議

1. 選擇包含數個專案的根目錄。
2. 展示 App 如何辨識不同 Agent 的原生檔案。
3. 進入記憶編程，選擇一個模組並填表。
4. 展示本機 Markdown 預覽與 Diff。
5. 套用並在歷史中復原。
6. 放入錯誤檔名或測試用假密碼，展示記憶健檢。

## 目前限制

- 不用本機 LLM，因此不提供語意摘要或自由文字智慧改寫。
- 健檢中的 token 是字元除以四的粗估值，不是官方 tokenizer 結果。
- 規格是版本化快照，需要後續人工查證更新。
- GitHub Copilot、Cursor、Windsurf 目前只列相容性資訊。
- Next App 尚未 Developer ID 簽章或 notarization。
